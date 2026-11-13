"""The web app is installable: manifest and service worker are served with the right type and caching."""

import httpx
import pytest

from acf import config
from acf.main import create_app


@pytest.fixture
async def web(tmp_path, monkeypatch):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>x</title>")
    (dist / "manifest.webmanifest").write_text('{"name": "AI Chatbot Framework"}')
    (dist / "sw.js").write_text("self.addEventListener('fetch', () => {});")
    (dist / "assets" / "index-abc123.js").write_text("console.log(1)")
    monkeypatch.setattr(config.settings, "frontend_dist", dist)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()), base_url="http://test") as c:
        yield c


async def test_manifest_is_served_as_a_web_manifest(web):
    r = await web.get("/manifest.webmanifest")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/manifest+json")
    assert r.json()["name"] == "AI Chatbot Framework"


async def test_service_worker_and_app_shell_are_always_revalidated(web):
    # A cached sw.js or index.html would pin users to an old build.
    sw = await web.get("/sw.js")
    assert sw.status_code == 200
    assert "javascript" in sw.headers["content-type"]
    assert sw.headers["cache-control"] == "no-cache"
    for path in ("/", "/c/12", "/index.html"):
        page = await web.get(path)
        assert page.status_code == 200 and page.headers["cache-control"] == "no-cache", path


async def test_hashed_assets_are_cached_for_good(web):
    r = await web.get("/assets/index-abc123.js")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"


async def test_api_misses_stay_json_404s(web):
    r = await web.get("/api/nope")
    assert r.status_code == 404 and r.json() == {"detail": "Not found"}
