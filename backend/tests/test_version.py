"""The running version is reported by the API and matches every place a release sets it."""

import json
import re
import tomllib
from pathlib import Path

from packaging.version import Version

import acf

ROOT = Path(__file__).resolve().parents[2]


async def test_health_reports_the_installed_version(client):
    r = await client.get("/api/health")
    assert r.json() == {"ok": True, "version": acf.__version__}


def test_the_version_is_shown_as_in_the_release_tag():
    assert [acf.semver(v) for v in ("2.0.0b1", "2.0.0rc2", "2.1.0", "3.0")] == [
        "2.0.0-beta.1",
        "2.0.0-rc.2",
        "2.1.0",
        "3.0.0",
    ]


def test_backend_and_frontend_versions_agree():
    backend = tomllib.loads((ROOT / "backend/pyproject.toml").read_text())["project"]["version"]
    frontend = json.loads((ROOT / "frontend/package.json").read_text())["version"]
    lock = json.loads((ROOT / "frontend/package-lock.json").read_text())
    assert acf.semver(backend) == frontend
    assert Version(backend) == Version(frontend) == Version(lock["version"]) == Version(lock["packages"][""]["version"])


def test_deploy_files_pull_the_images_of_this_version():
    frontend = json.loads((ROOT / "frontend/package.json").read_text())["version"]
    compose = (ROOT / "docker-compose.yml").read_text()
    defaults = set(re.findall(r"\$\{ACF_VERSION:-([^}]*)\}", compose))
    assert defaults == {frontend}
    assert re.search(rf"^ACF_VERSION={re.escape(frontend)}$", (ROOT / ".env.example").read_text(), re.M)
