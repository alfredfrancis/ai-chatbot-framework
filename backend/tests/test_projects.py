import asyncio
import json

from acf import workspace
from tests.conftest import send


async def _project(client, **fields) -> dict:
    r = await client.post("/api/projects", json={"name": "Website", **fields})
    assert r.status_code == 200, r.text
    return r.json()


async def _chat(client, project_id: int | None = None) -> int:
    return (await client.post("/api/chats", json={"project_id": project_id})).json()["id"]


async def _other_user(client) -> dict:
    """Sign up a second account on the same client; returns the cookies of the first to switch back."""
    mine = dict(client.cookies)
    client.cookies.clear()
    r = await client.post("/api/auth/signup", json={"email": f"o{id(mine)}@example.com", "password": "correct horse"})
    assert r.status_code == 200, r.text
    return mine


async def test_create_list_update_delete(client, user):
    assert (await client.post("/api/projects", json={"name": ""})).status_code == 422
    p = await _project(client, description="The new site", instructions="Write in British English.")
    assert p["name"] == "Website" and p["folder"] == "" and p["chats"] == 0 and p["tasks"] == 0

    r = await client.patch(f"/api/projects/{p['id']}", json={"name": "Site", "instructions": "Be brief."})
    assert r.json()["name"] == "Site" and r.json()["instructions"] == "Be brief."
    assert r.json()["description"] == "The new site"  # fields left out stay as they are

    listed = (await client.get("/api/projects")).json()
    assert [x["name"] for x in listed] == ["Site"]
    assert (await client.delete(f"/api/projects/{p['id']}")).status_code == 200
    assert (await client.get("/api/projects")).json() == []
    assert (await client.get(f"/api/projects/{p['id']}")).status_code == 404


async def test_folder_is_created_inside_the_workspace(client, user):
    p = await _project(client, folder="/workspace/projects/./site/")
    assert p["folder"] == "projects/site"
    assert workspace.resolve(user["id"], "projects/site").is_dir()

    for bad in ("../outside", "/", ".acf/chats", "context.md"):
        r = await client.post("/api/projects", json={"name": "x", "folder": bad})
        assert r.status_code == 400, bad
    # an existing folder is attached as it is; "" detaches it and the files stay
    workspace.write_file(user["id"], "notes/a.txt", "keep")
    r = await client.patch(f"/api/projects/{p['id']}", json={"folder": "notes"})
    assert r.json()["folder"] == "notes"
    assert (await client.patch(f"/api/projects/{p['id']}", json={"folder": ""})).json()["folder"] == ""
    assert workspace.read_file(user["id"], "notes/a.txt") == "keep"


async def test_project_chat_gets_instructions_and_folder(client, user):
    p = await _project(client, instructions="Always answer in pirate speak.", folder="projects/site")
    chat_id = await _chat(client, p["id"])
    turn = await send(client, chat_id, "show system")
    assert "Always answer in pirate speak." in turn.final
    assert f'<project id="{p["id"]}" name="Website">' in turn.final
    assert "/workspace/projects/site" in turn.final
    # a chat outside the project knows nothing of it
    plain = await send(client, await _chat(client), "show system")
    assert "pirate" not in plain.final and "<project" not in plain.final

    # edits reach the chat's next turn
    await client.patch(f"/api/projects/{p['id']}", json={"instructions": "Answer in haiku."})
    again = await send(client, chat_id, "show system")
    assert "Answer in haiku." in again.final and "pirate" not in again.final

    detail = (await client.get(f"/api/projects/{p['id']}")).json()
    assert [c["id"] for c in detail["chats"]] == [chat_id] and detail["project"]["chats"] == 1
    assert (await client.get(f"/api/chats/{chat_id}")).json()["project_id"] == p["id"]


async def test_acp_session_in_a_project(client, user):
    from tests.acp_client import RpcError, acp_connect
    from tests.conftest import prompt

    p = await _project(client, instructions="Sign off as Captain.")
    async with acp_connect(client) as acp:
        sid = (
            await acp.request("session/new", {"cwd": "/", "mcpServers": [], "_meta": {"acf": {"projectId": p["id"]}}})
        )["sessionId"]
        assert "Sign off as Captain." in (await prompt(acp, sid, "show system")).final
        loaded = await acp.request("session/load", {"sessionId": sid, "cwd": "/", "mcpServers": []})
        assert loaded["_meta"]["acf"]["project"] == {"id": p["id"], "name": "Website"}
        listed = (await acp.request("session/list", {}))["sessions"]
        assert next(s for s in listed if s["sessionId"] == sid)["_meta"]["acf"]["projectId"] == p["id"]
        try:
            await acp.request("session/new", {"_meta": {"acf": {"projectId": 10**9}}})
            raise AssertionError("an unknown project was accepted")
        except RpcError as e:
            assert "project" in e.message.lower()


async def test_project_task_runs_in_the_project(client, user):
    p = await _project(client, instructions="Report in one line.")
    r = await client.post(
        "/api/tasks", json={"name": "Digest", "prompt": "show system", "schedule": "0 9 * * *", "project_id": p["id"]}
    )
    assert r.status_code == 200, r.text
    task = r.json()
    assert task["project_id"] == p["id"]
    bad = await client.post(
        "/api/tasks", json={"name": "x", "prompt": "y", "schedule": "0 9 * * *", "project_id": 10**9}
    )
    assert bad.status_code == 400

    chat_id = (await client.post(f"/api/tasks/{task['id']}/run")).json()["chat_id"]
    for _ in range(100):
        t = next(x for x in (await client.get("/api/tasks")).json() if x["id"] == task["id"])
        if t["last_status"] in ("ok", "error"):
            break
        await asyncio.sleep(0.05)
    chat = (await client.get(f"/api/chats/{chat_id}")).json()
    assert chat["project_id"] == p["id"]
    assert "Report in one line." in chat["messages"][-1]["content"]

    detail = (await client.get(f"/api/projects/{p['id']}")).json()
    assert [t["name"] for t in detail["tasks"]] == ["Digest"] and detail["project"]["tasks"] == 1
    assert chat_id in [c["id"] for c in detail["chats"]]


async def test_agent_schedules_a_task_for_the_project(client, user):
    p = await _project(client)
    args = {"name": "Weekly", "prompt": "hi", "schedule": "0 9 * * 1", "timezone": "UTC", "project_id": p["id"]}
    call = {"server": "system", "tool": "create_task", "arguments": args}
    await send(client, await _chat(client, p["id"]), f"tool: mcp_call {json.dumps(call)}")
    tasks = (await client.get("/api/tasks")).json()
    assert [(t["name"], t["project_id"]) for t in tasks] == [("Weekly", p["id"])]

    call["arguments"] = {**args, "name": "Stray", "project_id": 10**9}
    turn = await send(client, await _chat(client), f"tool: mcp_call {json.dumps(call)}")
    assert "No project with id" in turn.final
    assert len((await client.get("/api/tasks")).json()) == 1


async def test_deleting_a_project_keeps_its_chats_tasks_and_files(client, user):
    p = await _project(client, folder="projects/keep")
    workspace.write_file(user["id"], "projects/keep/a.txt", "still here")
    chat_id = await _chat(client, p["id"])
    task = (
        await client.post(
            "/api/tasks", json={"name": "T", "prompt": "hi", "schedule": "0 9 * * *", "project_id": p["id"]}
        )
    ).json()
    await client.delete(f"/api/projects/{p['id']}")
    assert (await client.get(f"/api/chats/{chat_id}")).json()["project_id"] is None
    kept = next(t for t in (await client.get("/api/tasks")).json() if t["id"] == task["id"])
    assert kept["project_id"] is None
    assert workspace.read_file(user["id"], "projects/keep/a.txt") == "still here"
    assert "<project" not in (await send(client, chat_id, "show system")).final


async def test_projects_are_private(client, user):
    p = await _project(client, instructions="secret plan")
    mine = await _other_user(client)
    assert (await client.get("/api/projects")).json() == []
    assert (await client.get(f"/api/projects/{p['id']}")).status_code == 404
    assert (await client.patch(f"/api/projects/{p['id']}", json={"name": "x"})).status_code == 404
    assert (await client.delete(f"/api/projects/{p['id']}")).status_code == 404
    assert (await client.post("/api/chats", json={"project_id": p["id"]})).status_code == 404
    r = await client.post(
        "/api/tasks", json={"name": "x", "prompt": "y", "schedule": "0 9 * * *", "project_id": p["id"]}
    )
    assert r.status_code == 400
    client.cookies.clear()
    client.cookies.update(mine)
    assert (await client.get(f"/api/projects/{p['id']}")).status_code == 200
