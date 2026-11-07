#!/bin/sh
# Egress firewall for AI Chatbot Framework sandboxes. Run as root on the Docker host (not in a container),
# after Docker has started; acf-sandbox-firewall.service does that at boot. Safe to run again.
#
# Traffic from the sandbox bridge (ACF_SANDBOX_BRIDGE, default acf-sbx0) may reach the public internet
# only: private, shared, loopback, link-local (cloud metadata at 169.254.169.254), multicast and
# reserved addresses are rejected, as is the host itself. The host's DNS resolvers stay reachable on
# port 53 (Docker's embedded DNS forwards to them from the sandbox's network namespace).
#
#   ACF_SANDBOX_ALLOW="10.1.2.3/32 10.9.0.0/16"   extra destinations sandboxes may reach
#   sandbox-firewall.sh --remove                  take the rules out again
set -eu

BRIDGE="${ACF_SANDBOX_BRIDGE:-acf-sbx0}"
ALLOW="${ACF_SANDBOX_ALLOW:-}"
FWD=ACF-SANDBOX
IN=ACF-SANDBOX-IN
BLOCK="0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 127.0.0.0/8 169.254.0.0/16 172.16.0.0/12 192.0.0.0/24 192.0.2.0/24
192.88.99.0/24 192.168.0.0/16 198.18.0.0/15 198.51.100.0/24 203.0.113.0/24 224.0.0.0/4 240.0.0.0/4"

parent() {
  if iptables -n -L DOCKER-USER >/dev/null 2>&1; then echo DOCKER-USER; else echo FORWARD; fi
}

unhook() { # tool chain parent
  while "$1" -D "$3" -i "$BRIDGE" -j "$2" 2>/dev/null; do :; done
  "$1" -F "$2" 2>/dev/null || true
  "$1" -X "$2" 2>/dev/null || true
}

resolvers() {
  conf=/etc/resolv.conf
  [ -f /run/systemd/resolve/resolv.conf ] && conf=/run/systemd/resolve/resolv.conf
  awk '$1 == "nameserver" && $2 ~ /^[0-9.]+$/ && $2 !~ /^127\./ { print $2 }' "$conf"
}

P="$(parent)"
unhook iptables "$FWD" "$P"
unhook iptables "$IN" INPUT
if command -v ip6tables >/dev/null 2>&1; then
  unhook ip6tables "$FWD" FORWARD
  unhook ip6tables "$IN" INPUT
fi
if [ "${1:-}" = "--remove" ]; then
  echo "Sandbox firewall removed for $BRIDGE"
  exit 0
fi

iptables -N "$FWD"
for ns in $(resolvers); do
  iptables -A "$FWD" -d "$ns" -p udp --dport 53 -j RETURN
  iptables -A "$FWD" -d "$ns" -p tcp --dport 53 -j RETURN
done
for net in $ALLOW; do
  iptables -A "$FWD" -d "$net" -j RETURN
done
for net in $BLOCK; do
  iptables -A "$FWD" -d "$net" -j REJECT --reject-with icmp-net-prohibited
done
iptables -I "$P" 1 -i "$BRIDGE" -j "$FWD"

# The host itself (its services, published ports on its own addresses, the Docker API if exposed).
iptables -N "$IN"
iptables -A "$IN" -j REJECT --reject-with icmp-host-prohibited
iptables -I INPUT 1 -i "$BRIDGE" -j "$IN"

# The sandbox network has no IPv6; refuse it outright in case the host routes it.
if command -v ip6tables >/dev/null 2>&1; then
  for chain in "$FWD:FORWARD" "$IN:INPUT"; do
    ip6tables -N "${chain%%:*}"
    ip6tables -A "${chain%%:*}" -j REJECT
    ip6tables -I "${chain##*:}" 1 -i "$BRIDGE" -j "${chain%%:*}"
  done
fi
echo "Sandbox firewall active on $BRIDGE (forwarding chain: $P)"
