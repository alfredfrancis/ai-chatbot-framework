# The per-user sandbox image. Commands the agent runs and local (stdio) MCP servers run here.
# Includes Python, Node.js (npx) and uv (uvx) so most MCP servers start without extra setup.
# Extend it (FROM acf-sandbox) to add system packages your users need.
FROM node:22-slim AS node

FROM python:3.12-slim
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx \
 && pip install --no-cache-dir uv requests pandas openpyxl matplotlib

WORKDIR /workspace
CMD ["sleep", "infinity"]
