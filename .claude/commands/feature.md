---
description: Build a feature end to end (tests first, UI included) following AGENTS.md
argument-hint: <what to build>
---
Build this feature in Harbor: $ARGUMENTS

Follow AGENTS.md. In order:
1. Read the modules and tests this touches. State the plan in 3–6 bullets.
2. Write the failing tests first: a pytest for backend behaviour and a Playwright spec in
   `frontend/e2e/` that drives the UI by role/label. Extend `backend/tests/fakes/fake_llm.py` if the
   scripted model needs a new rule.
3. Implement backend, then UI using only the tokens in `frontend/src/styles.css`.
4. Run `make lint`, `make test`, `make e2e` (and `make e2e-docker` for sandbox/MCP changes). Fix until green.
5. Update README.md/docs if configuration or behaviour changed. Summarise what changed and how it was verified.
