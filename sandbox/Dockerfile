# The per-user sandbox image. Commands the agent runs and local (stdio) MCP servers run here.
# Includes Python, Node.js (npx) and uv (uvx) so most MCP servers start without extra setup,
# plus Chromium and the agent-browser CLI for browser automation.
# Extend it (FROM acf-sandbox) to add system packages your users need.
FROM node:22-slim AS node

FROM python:3.12-slim
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
 && pip install --no-cache-dir uv requests pandas openpyxl matplotlib

# curl (models reach for it first), Chromium from Debian (pulls in its system libraries) and
# agent-browser. The sandbox runs as a non-root user with every capability dropped, so these must be
# in the image: the agent cannot apt-get or npm install -g. Chrome's own sandbox needs namespaces we
# drop, hence --no-sandbox; Docker's 64 MB /dev/shm is too small for Chrome, hence --disable-dev-shm-usage.
ARG AGENT_BROWSER_VERSION=0.39.2
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl chromium fonts-liberation fonts-noto-color-emoji \
 && rm -rf /var/lib/apt/lists/* \
 && npm install -g agent-browser@${AGENT_BROWSER_VERSION} \
 && npm cache clean --force
ENV AGENT_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium \
    AGENT_BROWSER_ARGS=--no-sandbox,--disable-dev-shm-usage

WORKDIR /workspace
CMD ["sleep", "infinity"]
