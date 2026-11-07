# Preparing the Docker host

Every user's agent runs code in a sandbox container on this host. Before opening the server to people you
don't know, set up these four layers. The compose stack expects gVisor; the rest is host configuration.

| Layer | What it stops | Where |
|---|---|---|
| Docker proxy | A taken-over app using the Docker socket to get root on the host | `docker-proxy` service (`acf/docker_proxy.py`), automatic |
| gVisor (`runsc`) | Sandbox code attacking the host kernel directly | host install, below |
| User-namespace remapping | Container uids being host uids if something escapes | `/etc/docker/daemon.json`, below |
| Egress firewall | Sandboxes reaching the host, your private network or cloud metadata (instance credentials) | `sandbox-firewall.sh`, below |

The app itself runs as uid 10001 with no capabilities, and so do sandboxes. Sandboxes get their own bridge
network (`acf-sandbox`, interface `acf-sbx0`) with traffic between containers turned off.

## 1. gVisor

Debian/Ubuntu ([gVisor's install guide](https://gvisor.dev/docs/user_guide/install/)):

```sh
curl -fsSL https://gvisor.dev/archive.key | sudo gpg --dearmor -o /usr/share/keyrings/gvisor-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] https://storage.googleapis.com/gvisor/releases release main" \
  | sudo tee /etc/apt/sources.list.d/gvisor.list
sudo apt-get update && sudo apt-get install -y runsc
sudo runsc install          # registers the runsc runtime in /etc/docker/daemon.json
sudo systemctl restart docker
docker run --rm --runtime=runsc alpine uname -a   # should print a gVisor kernel
```

The stack uses `ACF_SANDBOX_RUNTIME=runsc` unless you set it in `.env`. `ACF_SANDBOX_RUNTIME=runc` turns
gVisor off; don't do that for a public server. Some programs don't run under gVisor (rare system calls,
some debugging tools); see its compatibility list.

## 2. User-namespace remapping

With remapping, uid 0 in any container is an unprivileged uid on the host (e.g. 100000).

```sh
echo '{ "userns-remap": "default" }' | sudo tee /etc/docker/daemon.json   # merge with what runsc install wrote
sudo systemctl restart docker
grep dockremap /etc/subuid          # e.g. dockremap:100000:65536 -> the base is 100000
```

Then set `ACF_DATA_UID` in `.env` to the base + 10001 (`110001` above), so the data folder belongs to the
app's user as the host sees it. Images are stored separately per remapping, so pull or build again after
turning it on. The Docker proxy and `data-init` services opt out (`userns_mode: host`): the proxy needs the
real socket, `data-init` only changes ownership of the data folder and has no network.

gVisor together with `userns-remap` has not been tested by this project. Check it after both are set up:
`docker run --rm --runtime=runsc alpine id`. If that fails, keep gVisor (the stronger layer) and leave
remapping off.

## 3. Egress firewall

```sh
sudo install -m 755 deploy/sandbox-firewall.sh /usr/local/sbin/acf-sandbox-firewall
sudo install -m 644 deploy/acf-sandbox-firewall.service /etc/systemd/system/
sudo systemctl enable --now acf-sandbox-firewall
```

Traffic from `acf-sbx0` may then only go to the public internet (and to the host's DNS resolvers on port
53). Private, link-local and reserved ranges are refused, including 169.254.169.254, and so is the host
itself. Allow extra destinations with `ACF_SANDBOX_ALLOW="10.1.2.3/32"` in the unit file. Set
`ACF_SANDBOX_NETWORK=none` instead to cut sandboxes off from the network completely.

Check it from a sandbox (Files → any chat): `run: python3 -c "import socket; socket.create_connection(('169.254.169.254', 80), 3)"`
should fail with "Network is unreachable".

## 4. The rest

- Set `ACF_SECRET_KEY` (`openssl rand -base64 48`). It encrypts users' API keys, MCP configurations and OAuth
  tokens in the database. Store it somewhere other than your database backups, and don't change it:
  stored secrets can't be read with another key.
- Leave `ANTHROPIC_API_KEY`/`ACF_LLM_API_KEY` empty if users should bring their own keys. When it is set,
  every user without a key of their own uses (and bills) yours. It is only sent to your provider and
  address; users who choose another provider or server must add their own key.
- Keep the host dedicated to this stack.
