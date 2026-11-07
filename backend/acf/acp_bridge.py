"""Connect a stdio ACP client (an editor, a CLI) to AI Chatbot Framework.

ACP clients usually start an agent as a subprocess and talk newline-delimited JSON-RPC over stdio. This
bridge is that subprocess: it forwards each stdin line to the server's ACP WebSocket and writes each
message it gets back as one stdout line.

    ACF_ACP_TOKEN=acp_… python -m acf.acp_bridge --url wss://agent.example.com/api/acp

Create the token in the web app: Settings → External apps.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

import websockets


async def bridge(url: str, token: str) -> int:
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        ws = await websockets.connect(url, additional_headers=headers, max_size=32 * 1024 * 1024)
    except websockets.InvalidStatus as e:
        print(
            f"acp-bridge: the server refused the connection ({e.response.status_code}). Check the token.",
            file=sys.stderr,
        )
        return 2
    except OSError as e:
        print(f"acp-bridge: could not connect to {url}: {e}", file=sys.stderr)
        return 2

    loop = asyncio.get_running_loop()
    reader = asyncio.StreamReader(limit=32 * 1024 * 1024)
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)

    async def upstream() -> None:
        while line := await reader.readline():
            if line.strip():
                await ws.send(line.decode().strip())

    async def downstream() -> None:
        async for msg in ws:
            text = msg if isinstance(msg, str) else msg.decode()
            sys.stdout.write(text.replace("\n", " ") + "\n")
            sys.stdout.flush()

    up, down = asyncio.create_task(upstream()), asyncio.create_task(downstream())
    # Ends when the client closes stdin or the server closes the connection.
    _, pending = await asyncio.wait({up, down}, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
    await ws.close()
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--url", default=os.environ.get("ACF_ACP_URL", "ws://localhost:8000/api/acp"))
    p.add_argument("--token", default=os.environ.get("ACF_ACP_TOKEN", ""), help="ACP access token (or ACF_ACP_TOKEN)")
    args = p.parse_args()
    sys.exit(asyncio.run(bridge(args.url, args.token)))


if __name__ == "__main__":
    main()
