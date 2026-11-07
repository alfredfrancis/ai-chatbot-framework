"""Security headers on every response; workspace files can't run as part of the app."""

from acf import workspace


async def test_api_responses_carry_security_headers(client):
    r = await client.get("/api/health")
    h = r.headers
    csp = h["content-security-policy"]
    assert "default-src 'self'" in csp and "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
    assert "connect-src 'self' ws://localhost:8000" in csp
    assert h["x-content-type-options"] == "nosniff"
    assert h["x-frame-options"] == "DENY"
    assert h["referrer-policy"] == "same-origin"
    assert "camera=()" in h["permissions-policy"]
    assert "cross-origin-opener-policy" not in h  # would break the OAuth popup (window.opener)
    assert "strict-transport-security" not in h  # plain http (development)


async def test_hsts_and_wss_on_https(monkeypatch):
    import httpx

    from acf import config
    from acf.main import create_app

    monkeypatch.setattr(config.settings, "public_url", "https://chat.example.com")
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        h = (await c.get("/api/health")).headers
    assert h["strict-transport-security"].startswith("max-age=31536000")
    assert "connect-src 'self' wss://chat.example.com" in h["content-security-policy"]


async def test_workspace_files_are_served_sandboxed(client, user):
    ws = workspace.workspace_dir(user["id"])
    (ws / "page.html").write_text("<script>alert(document.cookie)</script>")
    (ws / "doc.pdf").write_bytes(b"%PDF-1.4\n")
    r = await client.get("/api/files/raw", params={"path": "page.html"})
    assert r.status_code == 200
    csp = r.headers.get_list("content-security-policy")
    assert len(csp) == 1 and csp[0].startswith("sandbox;") and "script-src" not in csp[0]
    assert r.headers["x-content-type-options"] == "nosniff"
    pdf = await client.get("/api/files/raw", params={"path": "doc.pdf"})
    assert pdf.headers["content-type"] == "application/pdf" and "content-security-policy" not in pdf.headers
