"""FastAPI app: JSON API under /api, the built web app everywhere else."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from acf import acp, auth, bus, config, db, scheduler
from acf.agent import loop as agent
from acf.api.routes import router

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await bus.current().start()
    # Processes starting together take turns: creating tables, the main account and the secret key file.
    async with bus.current().hold("startup", timeout=300):
        db.init_db()
        with db.session_scope() as s:
            auth.ensure_admin(s)
    task = asyncio.create_task(scheduler.loop()) if config.settings.scheduler_enabled else None
    yield
    if task:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    # Scaling in or restarting: finish (or stop) this process's agents, then free its chats and locks.
    await agent.shutdown(config.settings.shutdown_grace)
    await bus.current().close()


# Workspace files are the user's (or the agent's) content: never run them as part of the app.
FILE_CSP = "sandbox; default-src 'none'; img-src 'self' data:; media-src 'self'; style-src 'unsafe-inline'"


def security_headers() -> list[tuple[bytes, bytes]]:
    public = urlparse(config.settings.public_url)
    ws = f"{'wss' if public.scheme == 'https' else 'ws'}://{public.netloc}"
    csp = "; ".join(
        [
            "default-src 'self'",
            "script-src 'self'",
            "style-src 'self' 'unsafe-inline'",  # React style attributes
            "img-src 'self' data: blob:",
            "font-src 'self' data:",
            f"connect-src 'self' {ws}",
            "object-src 'none'",
            "base-uri 'none'",
            "form-action 'self'",
            "frame-ancestors 'none'",
        ]
    )
    headers = {
        "content-security-policy": csp,
        "x-content-type-options": "nosniff",
        "x-frame-options": "DENY",
        "referrer-policy": "same-origin",
        "permissions-policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        # No Cross-Origin-Opener-Policy: the OAuth popup reports back through window.opener after
        # visiting the provider's site, which COOP would cut off.
    }
    if public.scheme == "https":
        headers["strict-transport-security"] = "max-age=31536000; includeSubDomains"
    return [(k.encode(), v.encode()) for k, v in headers.items()]


class SecurityHeaders:
    """Adds security headers to every HTTP response (plain ASGI, so streaming and WebSockets are untouched)."""

    def __init__(self, app):
        self.app = app
        self.headers = security_headers()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        is_file = scope["path"] == "/api/files/raw"

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                existing = {k.lower() for k, _ in message.get("headers", [])}
                extra = [(k, v) for k, v in self.headers if k not in existing]
                if is_file:
                    ctype = dict(message.get("headers", [])).get(b"content-type", b"")
                    extra = [(k, v) for k, v in extra if k != b"content-security-policy"]
                    if not ctype.startswith(b"application/pdf"):  # browsers' PDF viewers refuse sandboxed pages
                        extra.append((b"content-security-policy", FILE_CSP.encode()))
                message = {**message, "headers": [*message.get("headers", []), *extra]}
            await send(message)

        await self.app(scope, receive, send_with_headers)


# The app shell and the service worker must never be served stale, or users stay on an old build.
REVALIDATE = {"index.html", "sw.js"}
MEDIA_TYPES = {".webmanifest": "application/manifest+json"}  # not in every system's mime types


class ImmutableFiles(StaticFiles):
    """Vite's /assets: file names carry a content hash, so browsers may keep them for good."""

    def file_response(self, *args, **kwargs):
        response = super().file_response(*args, **kwargs)
        response.headers["cache-control"] = "public, max-age=31536000, immutable"
        return response


def create_app() -> FastAPI:
    app = FastAPI(title="AI Chatbot Framework", lifespan=lifespan)
    app.add_middleware(SecurityHeaders)
    app.include_router(router)
    app.include_router(acp.router)

    dist = config.settings.frontend_dist
    if (dist / "index.html").exists():
        if (dist / "assets").exists():
            app.mount("/assets", ImmutableFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse({"detail": "Not found"}, status_code=404)
            target = (dist / path).resolve()
            if not (path and target.is_file() and dist.resolve() in target.parents):
                target = dist / "index.html"
            headers = {"cache-control": "no-cache"} if target.name in REVALIDATE else None
            return FileResponse(target, media_type=MEDIA_TYPES.get(target.suffix), headers=headers)

    return app


app = create_app()
