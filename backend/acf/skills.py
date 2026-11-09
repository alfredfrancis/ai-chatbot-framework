"""Skills in the Agent Skills format: a folder with a SKILL.md whose YAML frontmatter has a `name` and
a `description`, plus any scripts or reference files it needs.

They live in the user's workspace under skills/<name>/ (so /workspace/skills/<name>/ in the sandbox).
Only names and descriptions go into the system prompt; the agent reads SKILL.md when a task needs it
(progressive disclosure). The agent can also write new skills itself, and fixes them as it learns.

Built-in skills (acf/builtin_skills/) are copied into a workspace once each: a user can change or delete
them, and a deleted one does not come back. Each read of a SKILL.md is recorded; a skill nobody read for
`skill_archive_days` moves to skills/.archive/ (never deleted). `pinned: true` in the frontmatter, and
skill-creator, keep a skill in place.
"""

from __future__ import annotations

import io
import json
import logging
import re
import shutil
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml

from acf import config, scan, workspace

log = logging.getLogger("acf.skills")
SKILLS_DIR = "skills"
ARCHIVE_DIR = ".archive"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MAX_ZIP_BYTES = 20 * 1024 * 1024
MAX_FILES = 500
BUILTIN = Path(__file__).parent / "builtin_skills"
STATE_FILE = ".acf/skills.json"  # {"seeded": [names], "used": {name: unix time}}
DAY = 86_400


@dataclass
class Skill:
    name: str
    description: str
    path: str  # relative to the workspace, e.g. skills/charts/SKILL.md
    files: int
    builtin: bool = False  # came with AI Chatbot Framework (acf/builtin_skills/), possibly changed since

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "path": self.path,
            "files": self.files,
            "builtin": self.builtin,
        }


class SkillError(ValueError):
    pass


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    try:
        data = yaml.safe_load(text[3:end]) or {}
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def skills_root(user_id: int) -> Path:
    root = workspace.workspace_dir(user_id) / SKILLS_DIR
    root.mkdir(exist_ok=True)
    return root


def _state(user_id: int) -> dict:
    try:
        data = json.loads(workspace.read_file(user_id, STATE_FILE) or "{}")
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}


def _save_state(user_id: int, data: dict) -> None:
    workspace.write_file(user_id, STATE_FILE, json.dumps(data, indent=1, sort_keys=True))


# A message can call a skill by name: "/pdf turn this into a report". The message is stored with one line
# per skill called, which tells the agent where the skill is; clients show the message as it was typed.
USE = "[Use skill: {name}](skills/{name}/SKILL.md)"
USE_RE = re.compile(r"^\[Use skill: ([a-z0-9-]+)\]\(skills/\1/SKILL\.md\)$\n?", re.MULTILINE)
# "/name" on its own: not part of a path or a URL (/etc/passwd, a/b, /pdf/SKILL.md, /pdf.txt).
REFERENCE_RE = re.compile(r"(?<![\w/.:-])/([a-z0-9][a-z0-9-]{0,63})(?!\.?[\w/-])")


def reference(user_id: int, text: str) -> str:
    """`text` with a "[Use skill: …]" line for every /name in it that is one of the user's skills."""
    called = list(dict.fromkeys(REFERENCE_RE.findall(USE_RE.sub("", text))))
    if not called:
        return text
    have = {s.name for s in list_skills(user_id)}
    lines = [USE.format(name=n) for n in called if n in have]
    lines = [line for line in lines if line not in text.splitlines()]
    if not lines:
        return text
    sep = "\n" if USE_RE.search(text) else "\n\n"
    return text.rstrip() + sep + "\n".join(lines)


def strip_references(text: str) -> str:
    """A stored message as the user typed it."""
    return USE_RE.sub("", text).strip() if "[Use skill: " in text else text


def builtin_names() -> list[str]:
    return sorted(p.parent.name for p in BUILTIN.glob("*/SKILL.md"))


def seed(user_id: int) -> None:
    """Copy each built-in skill into the workspace once (a skill the user deleted stays deleted)."""
    state = _state(user_id)
    seeded = set(state.get("seeded", []))
    root = skills_root(user_id)
    added = False
    for name in builtin_names():
        if name in seeded:
            continue
        if not (root / name).exists():
            shutil.copytree(BUILTIN / name, root / name)
        seeded.add(name)
        added = True
    if added:
        state["seeded"] = sorted(seeded)
        _save_state(user_id, state)


def record_use(user_id: int, rel: str) -> None:
    """Note that a skill's SKILL.md was read (rel is the path the agent read)."""
    try:
        parts = PurePosixPath(workspace.relative(user_id, rel)).parts
    except ValueError:
        return
    if len(parts) == 3 and parts[0] == SKILLS_DIR and parts[2] == "SKILL.md" and parts[1] != ARCHIVE_DIR:
        state = _state(user_id)
        state.setdefault("used", {})[parts[1]] = int(time.time())
        _save_state(user_id, state)


def archive_stale(user_id: int, now: float | None = None) -> list[str]:
    """Move skills unused for `skill_archive_days` to skills/.archive/. Returns the names moved.

    A skill's clock starts the first time this sees it, so new and existing skills get the full period."""
    days = config.settings.skill_archive_days
    if days <= 0:
        return []
    now = time.time() if now is None else now
    state = _state(user_id)
    used: dict = state.setdefault("used", {})
    root = skills_root(user_id)
    moved, changed = [], False
    for md in sorted(root.glob("*/SKILL.md")):
        name = md.parent.name
        if name not in used:
            used[name], changed = int(now), True
            continue
        if name == "skill-creator" or parse_frontmatter(md.read_text(errors="replace")).get("pinned") is True:
            continue
        if now - float(used[name]) < days * DAY:
            continue
        dest = root / ARCHIVE_DIR / name
        if dest.exists():
            dest = root / ARCHIVE_DIR / f"{name}-{int(now)}"
        dest.parent.mkdir(parents=True, exist_ok=True)
        md.parent.rename(dest)
        used.pop(name)
        moved.append(name)
        changed = True
    if changed:
        _save_state(user_id, state)
    if moved:
        log.info("archived unused skills for user %s: %s", user_id, ", ".join(moved))
    return moved


def list_skills(user_id: int) -> list[Skill]:
    root = skills_root(user_id)
    builtin = set(builtin_names())
    out = []
    for md in sorted(root.glob("*/SKILL.md")):
        meta = parse_frontmatter(md.read_text(errors="replace"))
        name = str(meta.get("name") or md.parent.name)
        desc = " ".join(str(meta.get("description") or "").split())
        files = sum(1 for p in md.parent.rglob("*") if p.is_file())
        path = f"{SKILLS_DIR}/{md.parent.name}/SKILL.md"
        out.append(Skill(name=name, description=desc, path=path, files=files, builtin=md.parent.name in builtin))
    return out


def _validate_skill_md(text: str, fallback: str) -> str:
    if found := scan.findings(text):
        raise SkillError(
            f"This skill contains text that looks like hidden instructions ({', '.join(found)}), so it was not added"
        )
    meta = parse_frontmatter(text)
    if not meta.get("description"):
        raise SkillError("SKILL.md needs YAML frontmatter with a name and a description")
    name = str(meta.get("name") or fallback).strip().lower()
    if not NAME_RE.match(name):
        raise SkillError(f'Skill name "{name}" must be lowercase letters, numbers and dashes')
    return name


def install(user_id: int, filename: str, data: bytes) -> Skill:
    """Install a skill from a .zip/.skill archive or a single SKILL.md. Replaces a skill of the same name."""
    root = skills_root(user_id)
    lower = filename.lower()
    if lower.endswith(".md"):
        text = data.decode("utf-8", errors="replace")
        name = _validate_skill_md(text, Path(filename).stem)
        dest = root / name
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)
        (dest / "SKILL.md").write_text(text)
    elif lower.endswith((".zip", ".skill")):
        if len(data) > MAX_ZIP_BYTES:
            raise SkillError("Skill archive is too large (max 20 MB)")
        try:
            zf = zipfile.ZipFile(io.BytesIO(data))
        except zipfile.BadZipFile as e:
            raise SkillError("That file is not a valid zip archive") from e
        names = [n for n in zf.namelist() if not n.endswith("/")]
        if len(names) > MAX_FILES:
            raise SkillError("Skill archive has too many files")
        candidates = sorted((n for n in names if PurePosixPath(n).name == "SKILL.md"), key=lambda n: n.count("/"))
        if not candidates:
            raise SkillError("No SKILL.md found in the archive")
        base = PurePosixPath(candidates[0]).parent
        text = zf.read(candidates[0]).decode("utf-8", errors="replace")
        name = _validate_skill_md(text, base.name or Path(filename).stem)
        dest = root / name
        staging = root / f".installing-{name}"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir()
        total = 0
        for n in names:
            p = PurePosixPath(n)
            if base.parts and p.parts[: len(base.parts)] != base.parts:
                continue
            rel = PurePosixPath(*p.parts[len(base.parts) :])
            if rel.is_absolute() or ".." in rel.parts or "__MACOSX" in rel.parts:
                continue
            content = zf.read(n)
            if rel.suffix.lower() == ".md" and (found := scan.findings(content.decode("utf-8", errors="replace"))):
                shutil.rmtree(staging)
                raise SkillError(
                    f"{rel} contains text that looks like hidden instructions ({', '.join(found)}), "
                    "so the skill was not added"
                )
            total += len(content)
            if total > MAX_ZIP_BYTES * 2:
                shutil.rmtree(staging)
                raise SkillError("Skill archive expands to more than 40 MB")
            out = staging / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(content)
        if dest.exists():
            shutil.rmtree(dest)
        staging.rename(dest)
    else:
        raise SkillError("Upload a .zip or .skill archive, or a SKILL.md file")
    return next(s for s in list_skills(user_id) if s.path == f"{SKILLS_DIR}/{name}/SKILL.md")


def remove(user_id: int, name: str) -> None:
    if not NAME_RE.match(name):
        raise SkillError("Invalid skill name")
    target = skills_root(user_id) / name
    if not target.is_dir():
        raise SkillError("No such skill")
    shutil.rmtree(target)
