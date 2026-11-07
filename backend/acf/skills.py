"""Skills in the Agent Skills format: a folder with a SKILL.md whose YAML frontmatter has a `name` and
a `description`, plus any scripts or reference files it needs.

They live in the user's workspace under skills/<name>/ (so /workspace/skills/<name>/ in the sandbox).
Only names and descriptions go into the system prompt; the agent reads SKILL.md when a task needs it
(progressive disclosure). The agent can also write new skills itself.
"""

from __future__ import annotations

import io
import re
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml

from acf import workspace

SKILLS_DIR = "skills"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
MAX_ZIP_BYTES = 20 * 1024 * 1024
MAX_FILES = 500

SKILL_CREATOR = """---
name: skill-creator
description: How to write a new skill. Use when the user asks you to remember how to do a task, to make a skill, or when you solved a multi-step task that is likely to come up again.
---

# Creating a skill

A skill is a folder `skills/<name>/` containing `SKILL.md` and optional helper files (scripts,
templates, reference notes).

1. Pick a short lowercase name with dashes, e.g. `weekly-report`.
2. Write `skills/<name>/SKILL.md`:

   ```
   ---
   name: weekly-report
   description: One or two sentences saying what it does AND when to use it.
   ---

   # Weekly report
   Step-by-step instructions, the exact commands to run, where inputs and outputs live,
   and what good output looks like.
   ```

3. Put scripts next to it (e.g. `skills/weekly-report/make_report.py`) and call them from the steps.
4. Keep SKILL.md short and concrete. Move long reference material into separate files and
   say when to read them.
5. Test the skill once by following it, then tell the user it exists.
"""


@dataclass
class Skill:
    name: str
    description: str
    path: str  # relative to the workspace, e.g. skills/charts/SKILL.md
    files: int

    def to_dict(self) -> dict:
        return {"name": self.name, "description": self.description, "path": self.path, "files": self.files}


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


def seed(user_id: int) -> None:
    """Give a new workspace the built-in skill-creator skill."""
    target = skills_root(user_id) / "skill-creator" / "SKILL.md"
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(SKILL_CREATOR)


def list_skills(user_id: int) -> list[Skill]:
    root = skills_root(user_id)
    out = []
    for md in sorted(root.glob("*/SKILL.md")):
        meta = parse_frontmatter(md.read_text(errors="replace"))
        name = str(meta.get("name") or md.parent.name)
        desc = " ".join(str(meta.get("description") or "").split())
        files = sum(1 for p in md.parent.rglob("*") if p.is_file())
        out.append(Skill(name=name, description=desc, path=f"{SKILLS_DIR}/{md.parent.name}/SKILL.md", files=files))
    return out


def _validate_skill_md(text: str, fallback: str) -> str:
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
