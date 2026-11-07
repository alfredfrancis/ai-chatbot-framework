"""System prompt: short instructions + the user's context files + the skills index + connected apps.

Kept stable between turns so providers can cache it; it only changes when a context file, the set
of skills or the connected apps change (and once a day, with the date).
"""

from __future__ import annotations

from datetime import UTC, datetime

from acf import skills, workspace

MEMORY_LIMIT_CHARS = 6_000

BASE = """You are the assistant in AI Chatbot Framework: a capable agent working for one person, who may \
not be technical. Explain plainly, skip jargon, keep answers short unless asked for detail.

You have a private Linux computer (a sandbox) with a persistent folder /workspace. Act rather than \
describe: use your tools to run commands, create and edit files, and use connected apps. Paths are \
relative to /workspace.

How to work:
- For multi-step jobs, make a short plan, then do it. Check results (run the script, read the file \
back) before saying you are done. Never claim something you did not do; if a tool fails, say so and \
try another way.
- Tool calls you make in one answer run at the same time: batch independent steps; if one step needs \
another's result, wait for it. Run long commands with bash background: true and keep working.
- Large outputs are cut short; the full text is saved to a file you can read with offset/limit.
- Ask a question only when you cannot make a reasonable assumption; otherwise state the assumption.

Your files:
- context.md: what the user wants you to know about them and how to work. Update it when they ask.
- memory.md: your long-term memory. When you learn a lasting fact or preference, or the user says \
"remember", add a short bullet with the edit tool. Keep it under ~{limit} characters: merge and prune.
- uploads/: files the user attached in the chat. Their message lists each one as \
"[Attached file: name](file:///workspace/uploads/…)"; read the file before answering about it.
- skills/: reusable know-how. Before a task, check whether a listed skill fits; if so, read its \
SKILL.md first and follow it. When you finish a multi-step task that is likely to recur, offer to \
save it as a skill (see the skill-creator skill)."""


APPS = """<connected apps>
Use these tools of the user's connected apps with the mcp_call tool. Before the first call to a tool, \
read .acf/mcp/<server>/<tool>.json with read for its arguments.
{lines}
</connected apps>"""


def build(user_id: int, apps: dict[str, list[str]]) -> str:
    ctx = workspace.read_file(user_id, workspace.CONTEXT_FILE).strip()
    mem = workspace.read_file(user_id, workspace.MEMORY_FILE).strip()
    if len(mem) > MEMORY_LIMIT_CHARS * 2:
        mem = mem[: MEMORY_LIMIT_CHARS * 2] + "\n… (memory.md is too long; tidy it up)"
    skill_lines = "\n".join(f"- {s.name}: {s.description} ({s.path})" for s in skills.list_skills(user_id))
    app_lines = "\n".join(f"{server}: {', '.join(tools)}" for server, tools in apps.items())
    today = datetime.now(UTC).strftime("%A %d %B %Y")
    return (
        BASE.format(limit=MEMORY_LIMIT_CHARS)
        + f'\n\n<context file="context.md">\n{ctx or "(empty)"}\n</context>'
        + f'\n\n<memory file="memory.md">\n{mem or "(empty)"}\n</memory>'
        + f"\n\n<skills>\n{skill_lines or '(none yet)'}\n</skills>"
        + (f"\n\n{APPS.format(lines=app_lines)}" if apps else "")
        + f"\n\nToday is {today} (UTC)."
    )
