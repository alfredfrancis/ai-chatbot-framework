# Harbor app image: API + built web UI in one container.
FROM node:22-slim AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM docker:29-cli AS dockercli

FROM python:3.12-slim
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
WORKDIR /app
COPY backend/pyproject.toml backend/
COPY backend/harbor backend/harbor
RUN pip install --no-cache-dir ./backend
COPY --from=web /web/dist /app/frontend/dist
ENV HARBOR_DATA_DIR=/data \
    HARBOR_FRONTEND_DIST=/app/frontend/dist
VOLUME /data
EXPOSE 8000
WORKDIR /app/backend
CMD ["uvicorn", "harbor.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
