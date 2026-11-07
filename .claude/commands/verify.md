---
description: Run every check Harbor's CI runs and report results honestly
---
Run, in order, and report each as pass/fail with the relevant output for failures:
1. `make lint`
2. `make test`
3. `make e2e-docker` if `docker info` succeeds, otherwise `make e2e` (say which one ran)

Do not change tests to make them pass. If something fails, diagnose the root cause and propose a fix.
