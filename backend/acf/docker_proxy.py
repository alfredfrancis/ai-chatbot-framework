"""A narrow Docker API proxy: the only way the app reaches Docker in production.

Giving the app the raw Docker socket gives whoever takes over the app root on the host (one privileged
container is enough). This proxy holds the socket instead and forwards only what DockerSandbox does,
with the exact settings it uses:

  - create a container named <prefix>-<user id> from the sandbox image, as a non-root user, with every
    capability dropped, no-new-privileges, resource limits, the configured runtime (e.g. gVisor) and
    network, and that user's workspace as its only mount
  - inspect, start and remove those containers; exec in them (not privileged, not as root)
  - inspect and create the sandbox network (inter-container traffic off)

Anything else (other images, privileged or host-namespace containers, other mounts, pulls, builds,
volumes, other containers) is refused with 403.

    python -m acf.docker_proxy --listen 0.0.0.0:2375 --socket /var/run/docker.sock

The app then uses DOCKER_HOST=tcp://<proxy>:2375. The policy comes from the same ACF_SANDBOX_*
settings as the app. Run it on a network only the app can reach.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, quote, urlsplit

import httpx

from acf import config
from acf.sandbox import PIDS_LIMIT

log = logging.getLogger("acf.docker_proxy")

MAX_HEAD = 64 * 1024
MAX_BODY = 1024 * 1024
HEAD_TIMEOUT = 30
_VERSION = re.compile(r"^/v\d+\.\d+(?=/)")
_UNITS = {"b": 1, "k": 1024, "m": 1024**2, "g": 1024**3}

# Network option values DockerSandbox creates the sandbox network with.
ICC = "com.docker.network.bridge.enable_icc"
BRIDGE_NAME = "com.docker.network.bridge.name"


class Denied(Exception):
    pass


def parse_bytes(value: str) -> int:
    m = re.fullmatch(r"(\d+)([bkmg]?)b?", value.strip().lower())
    if not m:
        raise ValueError(f"Bad size: {value}")
    return int(m.group(1)) * _UNITS[m.group(2) or "b"]


def empty(value: Any) -> bool:
    """Zero values the Docker CLI fills in for options that weren't given."""
    if isinstance(value, dict):
        return all(empty(v) for v in value.values())
    if isinstance(value, list):
        return all(empty(v) for v in value)
    return value in (None, "", 0, False)


@dataclass
class Policy:
    prefix: str
    image: str
    network: str
    bridge: str
    runtime: str
    bind_root: str
    memory: int
    nano_cpus: int
    _name: re.Pattern = field(init=False)

    def __post_init__(self) -> None:
        self._name = re.compile(rf"^/?{re.escape(self.prefix)}-(\d+)$")
        self.bind_root = self.bind_root.rstrip("/")

    @classmethod
    def from_settings(cls) -> Policy:
        s = config.settings
        return cls(
            prefix=s.sandbox_prefix,
            image=s.sandbox_image,
            network=s.sandbox_network,
            bridge=s.sandbox_bridge,
            runtime=s.sandbox_runtime,
            bind_root=s.sandbox_host_data_dir or str(s.data_dir),
            memory=parse_bytes(s.sandbox_memory),
            nano_cpus=int(float(s.sandbox_cpus) * 1e9),
        )

    def user_id(self, name: str) -> int | None:
        m = self._name.match(name or "")
        return int(m.group(1)) if m else None

    # -- request bodies

    def check_create(self, name: str, body: dict) -> None:
        uid = self.user_id(name)
        if uid is None:
            raise Denied(f"container name must be {self.prefix}-<user id>")
        if body.get("Image") != self.image:
            raise Denied(f"only the sandbox image {self.image} may be used")
        user = str(body.get("User") or "")
        m = re.fullmatch(r"(\d+)(?::(\d+))?", user)
        if not m or int(m.group(1)) == 0 or (m.group(2) is not None and int(m.group(2)) == 0):
            raise Denied("sandboxes must run as a non-root numeric user")
        labels = body.get("Labels") or {}
        if labels.get("acf.sandbox") != "1" or labels.get("acf.user") != str(uid):
            raise Denied("sandbox labels missing")
        for key in ("Entrypoint", "Volumes", "ExposedPorts"):
            if not empty(body.get(key)):
                raise Denied(f"{key} is not allowed")
        self._check_host_config(uid, body.get("HostConfig") or {})
        endpoints = ((body.get("NetworkingConfig") or {}).get("EndpointsConfig")) or {}
        if set(endpoints) - {self.network}:
            raise Denied("only the sandbox network may be joined")

    def _check_host_config(self, uid: int, hc: dict) -> None:
        bind = f"{self.bind_root}/users/{uid}/workspace:/workspace"
        checks = {
            "Binds": lambda v: v == [bind],
            "NetworkMode": lambda v: v == self.network,
            "CapDrop": lambda v: [c.upper() for c in v] == ["ALL"],
            "SecurityOpt": lambda v: bool(v) and set(v) <= {"no-new-privileges", "no-new-privileges:true"},
            "Memory": lambda v: 0 < v <= self.memory,
            "NanoCpus": lambda v: 0 < v <= self.nano_cpus,
            "PidsLimit": lambda v: 0 < v <= PIDS_LIMIT,
            "Runtime": lambda v: v == self.runtime,
            "RestartPolicy": lambda v: v.get("Name") in ("", "no") and empty(v.get("MaximumRetryCount")),
            "MemorySwappiness": lambda v: v == -1,  # the CLI's "default"
        }
        # An empty list here is not a default: it turns off Docker's masking of /proc and /sys paths.
        for key in ("MaskedPaths", "ReadonlyPaths"):
            if hc.get(key) is not None:
                raise Denied(f"HostConfig.{key} is not allowed")
        required = ["Binds", "NetworkMode", "CapDrop", "SecurityOpt", "Memory", "NanoCpus", "PidsLimit"]
        if self.runtime:
            required.append("Runtime")
        for key in required:
            if empty(hc.get(key)):
                raise Denied(f"HostConfig.{key} is required")
        for key, value in hc.items():
            if empty(value):
                continue
            check = checks.get(key)
            if check is None:
                raise Denied(f"HostConfig.{key} is not allowed")
            try:
                ok = check(value)
            except (TypeError, AttributeError):
                ok = False
            if not ok:
                raise Denied(f"HostConfig.{key} has a value that is not allowed")

    def check_exec(self, body: dict) -> None:
        if body.get("Privileged"):
            raise Denied("privileged exec is not allowed")
        user = str(body.get("User") or "")
        if user and (not re.fullmatch(r"[1-9]\d*(:[1-9]\d*)?", user)):
            raise Denied("exec must run as the sandbox's own user")

    def check_network_create(self, body: dict) -> None:
        if body.get("Name") != self.network:
            raise Denied("only the sandbox network may be created")
        if (body.get("Driver") or "bridge") != "bridge":
            raise Denied("the sandbox network must be a bridge")
        if body.get("Options") != {ICC: "false", BRIDGE_NAME: self.bridge}:
            raise Denied("the sandbox network must have inter-container traffic off")
        if (body.get("Labels") or {}).get("acf.sandbox") != "1":
            raise Denied("sandbox labels missing")
        for key in ("EnableIPv6", "Attachable", "Ingress", "ConfigOnly", "ConfigFrom", "Scope"):
            if not empty(body.get(key)) and not (key == "Scope" and body[key] == "local"):
                raise Denied(f"{key} is not allowed")


class Upstream:
    """Read-only lookups on the real Docker API, to tell whether an id belongs to a sandbox."""

    def __init__(self, socket: str):
        self.client = httpx.AsyncClient(transport=httpx.AsyncHTTPTransport(uds=socket), base_url="http://docker")

    async def get(self, path: str) -> dict | None:
        r = await self.client.get(path)
        return r.json() if r.status_code == 200 else None


class Proxy:
    def __init__(self, policy: Policy, socket: str):
        self.policy, self.socket = policy, socket
        self.upstream = Upstream(socket)
        self._handlers: set[asyncio.Task] = set()

    async def aclose(self) -> None:
        """Stop open connections (e.g. attached execs) and the upstream client."""
        for task in list(self._handlers):
            task.cancel()
        await asyncio.gather(*self._handlers, return_exceptions=True)
        await self.upstream.client.aclose()

    async def _own_container(self, ref: str) -> None:
        if self.policy.user_id(ref) is not None:
            return
        info = await self.upstream.get(f"/containers/{quote(ref, safe='')}/json")
        if info and self.policy.user_id(info.get("Name", "")) is not None:
            if (info.get("Config", {}).get("Labels") or {}).get("acf.sandbox") == "1":
                return
        raise Denied("not a sandbox container")

    async def _own_exec(self, exec_id: str) -> None:
        info = await self.upstream.get(f"/exec/{quote(exec_id, safe='')}/json")
        if not info:
            raise Denied("unknown exec")
        await self._own_container(info.get("ContainerID", ""))

    async def check(self, method: str, path: str, query: dict[str, list[str]], body: bytes) -> None:
        path = _VERSION.sub("", path)
        parts = [p for p in path.split("/") if p]

        def data() -> dict:
            try:
                parsed = json.loads(body or b"{}")
            except ValueError as e:
                raise Denied("body must be JSON") from e
            if not isinstance(parsed, dict):
                raise Denied("body must be a JSON object")
            return parsed

        if method in ("GET", "HEAD") and parts in (["_ping"], ["version"]):
            return
        if parts[:1] == ["containers"]:
            if method == "POST" and parts == ["containers", "create"]:
                return self.policy.check_create((query.get("name") or [""])[0], data())
            if len(parts) == 3 and method == "GET" and parts[2] == "json":
                return await self._own_container(parts[1])
            if len(parts) == 3 and method == "POST" and parts[2] in ("start", "stop", "kill", "wait"):
                return await self._own_container(parts[1])
            if len(parts) == 3 and method == "POST" and parts[2] == "exec":
                await self._own_container(parts[1])
                return self.policy.check_exec(data())
            if len(parts) == 2 and method == "DELETE":
                return await self._own_container(parts[1])
        if parts[:1] == ["exec"] and len(parts) == 3:
            if (method, parts[2]) in (("POST", "start"), ("POST", "resize"), ("GET", "json")):
                return await self._own_exec(parts[1])
        if parts[:1] == ["networks"]:
            if method == "POST" and parts == ["networks", "create"]:
                return self.policy.check_network_create(data())
            if method == "GET" and len(parts) == 2 and parts[1] == self.policy.network:
                return
        raise Denied(f"{method} {path} is not allowed")

    # -- HTTP plumbing

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()
        if task:
            self._handlers.add(task)
            task.add_done_callback(self._handlers.discard)
        try:
            await self._handle(reader, writer)
        except (asyncio.IncompleteReadError, asyncio.LimitOverrunError, ConnectionError, TimeoutError):
            pass
        except Exception:  # noqa: BLE001
            log.exception("docker proxy request failed")
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        head = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), HEAD_TIMEOUT)
        lines = head.decode("latin-1").split("\r\n")
        method, target, _version = lines[0].split(" ", 2)
        headers = [tuple(x.strip() for x in line.split(":", 1)) for line in lines[1:] if ":" in line]
        lower = {k.lower(): v for k, v in headers}
        if "chunked" in lower.get("transfer-encoding", "").lower():
            return await self._reply(writer, 411, "chunked request bodies are not supported")
        length = int(lower.get("content-length") or 0)
        if length > MAX_BODY:
            return await self._reply(writer, 413, "request body too large")
        body = await asyncio.wait_for(reader.readexactly(length), HEAD_TIMEOUT) if length else b""
        url = urlsplit(target)
        try:
            await self.check(method, url.path, parse_qs(url.query), body)
        except Denied as e:
            log.warning("denied %s %s: %s", method, url.path, e)
            return await self._reply(writer, 403, f"Blocked by the AI Chatbot Framework Docker proxy: {e}")

        upgrade = "upgrade" in lower.get("connection", "").lower()
        keep = [(k, v) for k, v in headers if k.lower() not in ("connection", "keep-alive", "proxy-connection")]
        keep.append(("Connection", "Upgrade" if upgrade else "close"))
        out = f"{method} {target} HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in keep) + "\r\n"
        up_reader, up_writer = await asyncio.open_unix_connection(self.socket)
        try:
            up_writer.write(out.encode("latin-1") + body)
            await up_writer.drain()
            down = asyncio.create_task(_pipe(up_reader, writer))
            up = asyncio.create_task(_pipe(reader, up_writer)) if upgrade else None
            try:  # with attached streams (exec -i), raw both ways once the daemon switches protocols
                await down
            finally:
                down.cancel()
                if up:
                    up.cancel()
                await asyncio.gather(down, *([up] if up else []), return_exceptions=True)
        finally:
            up_writer.close()

    async def _reply(self, writer: asyncio.StreamWriter, status: int, message: str) -> None:
        body = json.dumps({"message": message}).encode()
        reason = {403: "Forbidden", 411: "Length Required", 413: "Payload Too Large"}[status]
        writer.write(
            f"HTTP/1.1 {status} {reason}\r\nContent-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\nConnection: close\r\n\r\n".encode()
            + body
        )
        await writer.drain()


async def _pipe(src: asyncio.StreamReader, dst: asyncio.StreamWriter) -> None:
    try:
        while data := await src.read(65536):
            dst.write(data)
            await dst.drain()
        if dst.can_write_eof():
            dst.write_eof()
    except (OSError, RuntimeError):  # the other side went away (e.g. a stopped command)
        pass


async def serve(host: str, port: int, socket: str) -> tuple[asyncio.Server, Proxy]:
    proxy = Proxy(Policy.from_settings(), socket)
    return await asyncio.start_server(proxy.handle, host, port, limit=MAX_HEAD), proxy


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--listen", default="0.0.0.0:2375")
    parser.add_argument("--socket", default="/var/run/docker.sock")
    args = parser.parse_args()
    host, _, port = args.listen.rpartition(":")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    async def run() -> None:
        server, _ = await serve(host or "0.0.0.0", int(port), args.socket)
        log.info("Docker proxy on %s for %s", args.listen, args.socket)
        async with server:
            await server.serve_forever()

    asyncio.run(run())


if __name__ == "__main__":
    main()
