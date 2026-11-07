# Contributing

Thanks for helping AI Chatbot Framework. Start with [AGENTS.md](AGENTS.md): it explains the layout, the rules and the
design tokens, for people and coding agents alike.

1. Fork and clone, then `make setup`.
2. Create a branch: `git checkout -b feature/short-name`.
3. Write tests first. Anything users can see needs a Playwright test in `frontend/e2e/`; backend
   behaviour needs a pytest in `backend/tests/`.
4. `make lint test e2e` must pass (and `make e2e-docker` if you touched the sandbox or MCP).
5. Open a pull request describing what changed and how you tested it. Screenshots help for UI changes.

Please be kind in issues and reviews.
