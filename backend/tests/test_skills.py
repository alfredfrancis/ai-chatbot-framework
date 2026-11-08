import io
import zipfile

from acf import workspace
from tests.conftest import send

SKILL = b"""---
name: charts
description: Make bar charts from CSV files. Use when asked for a chart.
---
# Charts
Run `python skills/charts/chart.py <csv>`.
"""


def make_zip(files: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in files.items():
            z.writestr(name, data)
    return buf.getvalue()


BUILTIN = {
    "action-items",
    "cited-research",
    "pdf",
    "personal-apps",
    "personal-assistant",
    "plain-writing",
    "price-watch",
    "skill-creator",
    "weekly-review",
}


async def test_builtin_skills_seeded(client, user):
    names = {s["name"] for s in (await client.get("/api/skills")).json()}
    assert names == BUILTIN


async def test_upload_zip_skill_and_agent_sees_it(client, user):
    data = make_zip({"charts/SKILL.md": SKILL, "charts/chart.py": b"print('chart')", "__MACOSX/x": b"junk"})
    r = await client.post("/api/skills", files={"file": ("charts.zip", data)})
    assert r.status_code == 200, r.text
    assert r.json() == {
        "name": "charts",
        "description": "Make bar charts from CSV files. Use when asked for a chart.",
        "path": "skills/charts/SKILL.md",
        "files": 2,
    }
    ws = workspace.workspace_dir(user["id"])
    assert (ws / "skills/charts/chart.py").read_text() == "print('chart')"
    assert not (ws / "skills/charts/__MACOSX").exists()

    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    system = (await send(client, chat_id, "show system")).final
    assert "- charts: Make bar charts from CSV files. Use when asked for a chart. (skills/charts/SKILL.md)" in system

    assert (await client.delete("/api/skills/charts")).status_code == 200
    assert {s["name"] for s in (await client.get("/api/skills")).json()} == BUILTIN


async def test_upload_single_skill_md(client, user):
    r = await client.post("/api/skills", files={"file": ("SKILL.md", SKILL)})
    assert r.status_code == 200 and r.json()["name"] == "charts"


async def test_invalid_skills_rejected(client, user):
    cases = [
        ("notes.txt", b"hi", "Upload a .zip"),
        ("x.zip", b"not a zip", "not a valid zip"),
        ("x.zip", make_zip({"readme.md": b"x"}), "No SKILL.md"),
        ("SKILL.md", b"# no frontmatter", "frontmatter"),
        ("SKILL.md", b"---\nname: Bad Name\ndescription: x\n---\n", "lowercase"),
    ]
    for name, data, msg in cases:
        r = await client.post("/api/skills", files={"file": (name, data)})
        assert r.status_code == 400 and msg in r.json()["detail"], (name, r.text)


async def test_zip_path_traversal_is_ignored(client, user):
    data = make_zip({"evil/SKILL.md": b"---\nname: evil\ndescription: x\n---\n", "evil/../../../escape.txt": b"x"})
    r = await client.post("/api/skills", files={"file": ("evil.zip", data)})
    assert r.status_code == 200
    assert not (workspace.workspace_dir(user["id"]).parent / "escape.txt").exists()
    assert not (workspace.workspace_dir(user["id"]) / "escape.txt").exists()


async def test_agent_can_create_a_skill(client, user):
    chat_id = (await client.post("/api/chats", json={})).json()["id"]
    md = "---\\nname: greet\\ndescription: Say hello. Use when greeting.\\n---\\n# Greet"
    await send(client, chat_id, f'tool: write {{"path": "skills/greet/SKILL.md", "content": "{md}"}}')
    assert "greet" in [s["name"] for s in (await client.get("/api/skills")).json()]
