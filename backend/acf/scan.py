"""A light check for prompt injection in text that is loaded into every system prompt (memory.md, skills).

Web pages, uploads and app results can carry instructions meant for the agent. If the agent copied one
into memory.md or a skill, it would steer every later chat. Writes of such text to those files are
refused (agent.tools), uploaded skills that contain it are rejected (skills.install), and memory.md that
contains it is not loaded (agent.prompt). The patterns are narrow on purpose: false positives block real
work. This is a tripwire, not a guarantee; isolation is the real boundary.
"""

from __future__ import annotations

import re

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore previous instructions",
        re.compile(
            r"\b(ignore|disregard|forget|override)\s+(all\s+|any\s+)?(of\s+)?(the\s+|your\s+)?"
            r"(previous|prior|above|earlier|system|original)\s+(instructions|prompts?|rules|messages)",
            re.I,
        ),
    ),
    (
        "hide from the user",
        re.compile(
            r"\b(do\s+not|don't|never)\s+(tell|inform|show|mention\s+(this\s+)?to)\s+the\s+user(?![\w'’])", re.I
        ),
    ),
    (
        "reveal the system prompt",
        re.compile(r"\b(reveal|print|output|repeat|send)\s+(your|the)\s+(system\s+prompt|instructions)\b", re.I),
    ),
    (
        "send secrets to a server",
        re.compile(
            r"\b(curl|wget|fetch|requests\.(get|post))\b[^\n]{0,200}"
            r"(\$\(\s*(cat|env|printenv)\b|\$\{?[A-Z_]*(KEY|TOKEN|SECRET|PASSWORD)\b|\.env\b|id_rsa|\.ssh/)",
            re.I,
        ),
    ),
    # Bidi overrides (text that reads differently than it displays) and tag characters (invisible ASCII).
    ("hidden characters", re.compile("[\u202a-\u202e\u2066-\u2069\U000e0000-\U000e007f]")),
]


def findings(text: str) -> list[str]:
    """Names of the patterns `text` matches (empty when it looks clean)."""
    return [name for name, pattern in PATTERNS if pattern.search(text)]


def guarded(rel: str) -> bool:
    """Files whose content goes into every system prompt or is followed as instructions (`rel` is
    normalised, see workspace.relative)."""
    return rel == "memory.md" or (rel.startswith("skills/") and rel.endswith(".md"))
