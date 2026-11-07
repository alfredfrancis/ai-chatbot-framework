async def test_browse_preview_download_upload(client, user):
    root = (await client.get("/api/files")).json()
    names = {e["name"]: e for e in root["entries"]}
    assert names["skills"]["type"] == "dir" and names["context.md"]["type"] == "file"
    assert list(names)[0] == "skills"  # folders first

    r = await client.post("/api/files", files={"file": ("sales.csv", b"a,b\n1,2\n")}, data={"folder": "data"})
    assert r.json() == {"path": "data/sales.csv", "size": 8}
    sub = (await client.get("/api/files", params={"path": "data"})).json()
    assert sub["path"] == "data" and sub["entries"][0]["name"] == "sales.csv"

    c = (await client.get("/api/files/content", params={"path": "data/sales.csv"})).json()
    assert c["content"] == "a,b\n1,2\n" and not c["binary"]
    raw = await client.get("/api/files/raw", params={"path": "data/sales.csv", "download": True})
    assert raw.content == b"a,b\n1,2\n" and "attachment" in raw.headers["content-disposition"]

    await client.post("/api/files", files={"file": ("x.bin", b"\0\1\2")})
    assert (await client.get("/api/files/content", params={"path": "x.bin"})).json()["binary"] is True


async def test_files_are_private_and_contained(client, user):
    assert (await client.get("/api/files", params={"path": "../.."})).status_code == 400
    assert (await client.get("/api/files/content", params={"path": "../x"})).status_code == 400
    bad = await client.post("/api/files", files={"file": ("x.txt", b"x")}, data={"folder": "../.."})
    assert bad.status_code == 400
    # there is no endpoint to edit context.md directly: edits go through the agent
    assert (await client.put("/api/memory/context", json={"content": "x"})).status_code in (404, 405)
