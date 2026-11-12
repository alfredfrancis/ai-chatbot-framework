"""Set the release version everywhere it lives: python3 scripts/set_version.py 2.0.0-beta.2

The version is SemVer (as in the git tag, without the "v"); pyproject.toml gets its PEP 440 form.
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEMVER = re.compile(r"(\d+)\.(\d+)\.(\d+)(?:-(beta|rc)\.(\d+))?")


def pep440(v: str) -> str:
    m = SEMVER.fullmatch(v)
    if not m:
        sys.exit(f"{v!r} is not X.Y.Z, X.Y.Z-beta.N or X.Y.Z-rc.N")
    major, minor, patch, pre, n = m.groups()
    return f"{major}.{minor}.{patch}" + ({"beta": "b", "rc": "rc"}[pre] + n if pre else "")


def sub(path: str, pattern: str, repl: str, count: int = 1) -> None:
    p = ROOT / path
    text, n = re.subn(pattern, repl, p.read_text(), count=count, flags=re.M)
    if n != count:
        sys.exit(f"{path}: expected {count} match(es) for {pattern!r}, found {n}")
    p.write_text(text)


def main(v: str) -> None:
    sub("backend/pyproject.toml", r'^version = ".*"$', f'version = "{pep440(v)}"')
    pkg = ROOT / "frontend/package.json"
    data = json.loads(pkg.read_text())
    data["version"] = v
    pkg.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    lock = ROOT / "frontend/package-lock.json"
    data = json.loads(lock.read_text())
    data["version"] = data["packages"][""]["version"] = v
    lock.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    sub("docker-compose.yml", r"\$\{ACF_VERSION:-[^}]*\}", f"${{ACF_VERSION:-{v}}}", count=5)
    sub(".env.example", r"^ACF_VERSION=.*$", f"ACF_VERSION={v}")
    print(f"Version set to {v} ({pep440(v)} for Python). Commit, merge, then publish release v{v}.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
