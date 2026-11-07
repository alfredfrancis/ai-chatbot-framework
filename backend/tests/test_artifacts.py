"""A chat's artifacts: files attached to it and files the agent made in it."""

import json
import os
import time

from acf import workspace
from tests.acp_client import acp_connect
from tests.conftest import prompt, send


async def new_chat(client) -> int:
    return (await client.post("/api/chats", json={})).json()["id"]


def bash(command: str, background: bool = False) -> str:
    return "tool: bash " + json.dumps({"command": command, **({"background": True} if background else {})})


def age_workspace(user_id: int) -> None:
    """Make the files a new account starts with older (a test runs its first command within milliseconds)."""
    past = time.time() - 60
    for p in workspace.workspace_dir(user_id).rglob("*"):
        os.utime(p, (past, past))


async def artifacts(client, chat_id: int) -> list[tuple[str, str]]:
    r = await client.get(f"/api/chats/{chat_id}/artifacts")
    assert r.status_code == 200, r.text
    return [(a["kind"], a["path"]) for a in r.json()]


async def test_uploaded_and_produced_files(client, user):
    up = await client.post(
        "/api/files", files={"file": ("a (1).csv", b"day,eur\n")}, data={"folder": "uploads", "keep": "true"}
    )
    path = up.json()["path"]
    workspace.resolve(user["id"], "old.txt").write_text("made before the chat")
    age_workspace(user["id"])

    chat_id = await new_chat(client)
    other = await new_chat(client)
    link = {"type": "resource_link", "uri": "file:///workspace/uploads/a%20%281%29.csv", "name": "a (1).csv"}
    async with acp_connect(client) as acp:
        await acp.request(
            "session/prompt", {"sessionId": str(chat_id), "prompt": [{"type": "text", "text": "hi"}, link]}
        )
    assert path == "uploads/a (1).csv"

    await send(client, chat_id, "write: report.md | # Sales")
    await send(client, chat_id, "edit: report.md | Sales | Weekly sales")
    await send(client, chat_id, "run: mkdir -p out && echo 1 > out/chart.txt && echo x > .hidden && cat old.txt")
    await send(client, chat_id, "write: memory.md | steering files are not artifacts")
    await send(client, chat_id, "write: gone.txt | x")
    workspace.resolve(user["id"], "gone.txt").unlink()  # deleted since: not listed
    await send(client, other, "write: elsewhere.txt | other chat")

    rows = (await client.get(f"/api/chats/{chat_id}/artifacts")).json()
    assert [(a["kind"], a["path"]) for a in rows] == [
        ("uploaded", "uploads/a (1).csv"),
        ("produced", "report.md"),
        ("produced", "out/chart.txt"),
    ]
    assert rows[0]["name"] == "a (1).csv" and rows[0]["size"] == 8 and rows[0]["modified_at"].endswith("Z")
    assert await artifacts(client, other) == [("produced", "elsewhere.txt")]


async def test_files_made_by_a_background_command(client, user):
    age_workspace(user["id"])
    chat_id = await new_chat(client)
    async with acp_connect(client) as acp:
        # the command outlives its tool call: the file counts because the job was still running
        await prompt(acp, chat_id, bash("sleep 1; echo done > bg.txt", background=True))
        await acp.wait_for(lambda n: sum(x["method"] == "_acf/turn_end" for x in acp.notifications) == 2, timeout=10)
    assert await artifacts(client, chat_id) == [("produced", "bg.txt")]


async def test_artifacts_are_private(client, user):
    chat_id = await new_chat(client)
    assert await artifacts(client, chat_id) == []
    await client.post("/api/auth/logout")
    await client.post("/api/auth/signup", json={"email": f"x{time.time_ns()}@example.com", "password": "correct horse"})
    assert (await client.get(f"/api/chats/{chat_id}/artifacts")).status_code == 404
