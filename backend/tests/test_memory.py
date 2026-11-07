async def test_default_files_and_edit(client, user):
    mem = (await client.get("/api/memory")).json()
    assert mem["context"].startswith("# About me")
    assert mem["memory"].startswith("# Memory")
    r = await client.put("/api/memory/memory", json={"content": "- likes tea\n"})
    assert r.status_code == 200
    assert (await client.get("/api/memory")).json()["memory"] == "- likes tea\n"
    assert (await client.put("/api/memory/other", json={"content": "x"})).status_code == 404


async def test_file_content_endpoint_blocks_escape(client, user):
    assert (await client.get("/api/files/content", params={"path": "context.md"})).status_code == 200
    assert (await client.get("/api/files/content", params={"path": "../x"})).status_code == 400


async def test_upload_file(client, user):
    r = await client.post("/api/files", files={"file": ("sales.csv", b"a,b\n1,2\n")}, data={"folder": "data"})
    assert r.status_code == 200 and r.json() == {"path": "data/sales.csv", "size": 8}
    assert {"path": "data/sales.csv", "size": 8} in (await client.get("/api/files")).json()
    bad = await client.post("/api/files", files={"file": ("x.txt", b"x")}, data={"folder": "../.."})
    assert bad.status_code == 400
