"""A remote MCP server (Streamable HTTP) protected by OAuth 2.1 with PKCE and dynamic client
registration. It is its own authorization server. The /authorize page shows an "Allow" button.

Run standalone: python -m tests.fakes.oauth_mcp --port 9200
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import secrets
from urllib.parse import urlencode

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route

CLIENTS: dict[str, dict] = {}
CODES: dict[str, dict] = {}
TOKENS: set[str] = set()
REFRESH: dict[str, str] = {}

mcp = MCPServer("notes")


@mcp.tool()
def get_secret_note() -> str:
    """Return the user's secret note (only visible after signing in)."""
    return "The secret note says: pineapple"


def _base(request: Request) -> str:
    return f"{request.url.scheme}://{request.url.netloc}"


async def protected_resource(request: Request):
    return JSONResponse({"resource": _base(request) + "/mcp", "authorization_servers": [_base(request)]})


async def as_metadata(request: Request):
    b = _base(request)
    return JSONResponse(
        {
            "issuer": b,
            "authorization_endpoint": b + "/authorize",
            "token_endpoint": b + "/token",
            "registration_endpoint": b + "/register",
            "code_challenge_methods_supported": ["S256"],
            "scopes_supported": ["notes"],
        }
    )


async def register(request: Request):
    body = await request.json()
    client_id = "client_" + secrets.token_hex(6)
    CLIENTS[client_id] = body
    return JSONResponse({"client_id": client_id, **body}, status_code=201)


async def authorize(request: Request):
    q = request.query_params
    if q.get("client_id") not in CLIENTS or q.get("code_challenge_method") != "S256":
        return HTMLResponse("bad request", status_code=400)
    if q.get("redirect_uri") not in CLIENTS[q["client_id"]].get("redirect_uris", []):
        return HTMLResponse("redirect_uri mismatch", status_code=400)
    code = secrets.token_urlsafe(16)
    CODES[code] = {
        "challenge": q["code_challenge"],
        "client_id": q["client_id"],
        "redirect_uri": q["redirect_uri"],
    }
    target = q["redirect_uri"] + "?" + urlencode({"code": code, "state": q.get("state", "")})
    return HTMLResponse(
        f"""<!doctype html><html><body style="font-family:sans-serif;padding:40px">
<h1>Notes wants access</h1><p>AI Chatbot Framework is asking to read your notes.</p>
<a id="allow" href="{html.escape(target)}">Allow access</a></body></html>"""
    )


async def token(request: Request):
    form = await request.form()
    if form.get("grant_type") == "authorization_code":
        info = CODES.pop(str(form.get("code")), None)
        if not info:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
        verifier = str(form.get("code_verifier", ""))
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
        if challenge != info["challenge"] or form.get("redirect_uri") != info["redirect_uri"]:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
    elif form.get("grant_type") == "refresh_token":
        if str(form.get("refresh_token")) not in REFRESH:
            return JSONResponse({"error": "invalid_grant"}, status_code=400)
    else:
        return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
    access, refresh = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
    TOKENS.add(access)
    REFRESH[refresh] = access
    return JSONResponse({"access_token": access, "token_type": "Bearer", "expires_in": 3600, "refresh_token": refresh})


class RequireBearer:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope["headers"])
            auth = headers.get(b"authorization", b"").decode()
            if not auth.startswith("Bearer ") or auth[7:] not in TOKENS:
                host = headers.get(b"host", b"localhost").decode()
                resp = JSONResponse(
                    {"error": "unauthorized"},
                    status_code=401,
                    headers={
                        "WWW-Authenticate": f'Bearer resource_metadata="http://{host}/.well-known/oauth-protected-resource"'
                    },
                )
                await resp(scope, receive, send)
                return
        await self.app(scope, receive, send)


mcp_app = mcp.streamable_http_app(
    streamable_http_path="/",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

app = Starlette(
    routes=[
        Route("/.well-known/oauth-protected-resource", protected_resource),
        Route("/.well-known/oauth-protected-resource/mcp", protected_resource),
        Route("/.well-known/oauth-authorization-server", as_metadata),
        Route("/register", register, methods=["POST"]),
        Route("/authorize", authorize),
        Route("/token", token, methods=["POST"]),
    ],
    lifespan=lambda _app: mcp_app.router.lifespan_context(mcp_app),
)
_protected = RequireBearer(mcp_app)
_starlette = app


async def app(scope, receive, send):  # noqa: F811 - outer dispatcher
    """Serve the MCP endpoint at exactly /mcp (no redirects), everything else via Starlette."""
    if scope["type"] == "http" and scope["path"].rstrip("/") == "/mcp":
        scope = {**scope, "path": "/", "raw_path": b"/"}
        await _protected(scope, receive, send)
        return
    await _starlette(scope, receive, send)


if __name__ == "__main__":
    import uvicorn

    p = argparse.ArgumentParser()
    p.add_argument("--port", type=int, default=9200)
    uvicorn.run(app, host="127.0.0.1", port=p.parse_args().port, log_level="warning")
