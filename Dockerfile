# AI Chatbot Framework app image: API + built web UI in one container.
FROM node:22-slim AS web
WORKDIR /web
# @openuidev/lang-core reports installs to PostHog unless this is set.
ENV OPENUI_TELEMETRY_DISABLED=1
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
COPY design/ /design/
RUN npm run build

FROM docker:29-cli AS dockercli

FROM python:3.12-slim
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
# The app runs as this user; its sandboxes run as it too (never as root). The docker-proxy service
# runs the same image as root, because it alone holds the Docker socket.
RUN useradd --uid 10001 --user-group --no-create-home --home-dir /data acf
WORKDIR /app
COPY backend/pyproject.toml backend/
COPY backend/acf backend/acf
RUN pip install --no-cache-dir ./backend
COPY --from=web /web/dist /app/frontend/dist
ENV ACF_DATA_DIR=/data \
    ACF_FRONTEND_DIST=/app/frontend/dist \
    DOCKER_CONFIG=/tmp/.docker
RUN mkdir -p /data && chown acf:acf /data
VOLUME /data
EXPOSE 8000
WORKDIR /app/backend
USER 10001:10001
CMD ["uvicorn", "acf.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
