---
description: Screenshot every Harbor screen (light, dark, phone) and review against the design rules
---
Build the web app (`cd frontend && npm run build`), start the fake model
(`cd backend && ../.venv/bin/python -m tests.fakes.fake_llm --port 9100`) and Harbor
(`bash frontend/e2e/start-harbor.sh`). With Playwright, sign up and capture Chat, Tasks, Connections,
Memory and Settings at 1280×800 in light and dark mode and at 390×844.

Review them against AGENTS.md rule 7 (tokens, spacing, contrast ≥ 4.5:1, no overflow at phone width,
accessible names). List concrete issues with file:line fixes; don't change unrelated code.
