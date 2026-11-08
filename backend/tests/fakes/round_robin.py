"""A tiny TCP load balancer for tests: each new connection goes to the next backend (skipping ones that
refuse). Stands in for Caddy in front of several app processes.

Run standalone: python -m tests.fakes.round_robin --listen 8765 --to 8766,8767
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import itertools


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while data := await reader.read(65536):
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        with contextlib.suppress(Exception):
            writer.close()


async def serve(listen: int, backends: list[int]) -> None:
    turn = itertools.cycle(backends)

    async def handle(client_r: asyncio.StreamReader, client_w: asyncio.StreamWriter) -> None:
        for _ in backends:
            port = next(turn)
            try:
                up_r, up_w = await asyncio.open_connection("127.0.0.1", port)
                break
            except OSError:
                continue
        else:
            client_w.close()
            return
        await asyncio.gather(_pipe(client_r, up_w), _pipe(up_r, client_w))

    server = await asyncio.start_server(handle, "127.0.0.1", listen)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--listen", type=int, required=True)
    ap.add_argument("--to", required=True, help="comma-separated backend ports")
    args = ap.parse_args()
    asyncio.run(serve(args.listen, [int(p) for p in args.to.split(",")]))
