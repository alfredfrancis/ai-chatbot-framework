# Versions and releases

AI Chatbot Framework 2.x is a rewrite. It shares nothing with the 1.0.0-alpha NLU framework: no data, config
or API carries over, and there is no upgrade path from 1.x. The 1.x code is kept on the
[`v1`](https://github.com/alfredfrancis/ai-chatbot-framework/tree/v1) branch and its images stay on Docker Hub
under the `1` tag (`ACF_VERSION=1`). It is not maintained.

## Version numbers

One version covers the whole project (app image, sandbox image, backend and web app). It follows
[SemVer](https://semver.org), with these rules for what counts as breaking:

| Bump  | When |
|-------|------|
| Major | An `ACF_*` setting is removed or renamed; a migration needs a manual step or can't be undone; ACP, the `SKILL.md` format, MCP config, the personal app format or the sandbox image change incompatibly |
| Minor | New features, new optional settings, migrations that only add |
| Patch | Fixes and security updates; no schema changes |

Pre-releases are `X.Y.Z-beta.N` (features may still change) and `X.Y.Z-rc.N` (only fixes).
Only the newest minor release gets fixes.

## Docker image tags

| Tag            | Moves on |
|----------------|----------|
| `2.1.3`, `2.1.0-beta.1` | never |
| `2.1`          | patch releases of 2.1 |
| `2`            | every stable 2.x release |
| `latest`       | every stable release |

Pre-releases are only published under their exact tag. `docker-compose.yml` and `.env.example` default
to the version of the checkout, so a deployment only moves when you change `ACF_VERSION`.

Upgrading: set `ACF_VERSION`, then `docker compose pull && docker compose up -d`. Migrations run at startup;
back up the database and `./data` first, and read the release notes for anything marked breaking.

## Making a release

1. `make version v=2.1.0` on a branch (it updates `backend/pyproject.toml`, `frontend/package.json`,
   its lockfile, `docker-compose.yml` and `.env.example`), merge it once CI is green.
2. Publish a GitHub release from `master` tagged `v2.1.0`, with generated notes. Tick **pre-release** for
   `-beta.N` / `-rc.N` tags (and only for those). Put anything breaking at the top.
3. The `Release images` workflow checks the tag against the version files and pushes both images.
