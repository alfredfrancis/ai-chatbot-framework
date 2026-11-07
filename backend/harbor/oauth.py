"""OAuth 2.1 client for remote MCP servers (authorization code + PKCE).

Flow (the browser does the redirect part):
1. Frontend calls POST /api/mcp/servers/{name}/oauth/start with its origin.
2. Harbor discovers the authorization server (RFC 9728 + RFC 8414), registers itself as a client
   (RFC 7591 dynamic registration) unless a client_id is configured, and returns the authorize URL.
3. The user signs in; the provider redirects to <origin>/oauth/callback?code=…&state=….
4. That frontend page posts code+state to POST /api/oauth/callback; Harbor exchanges the code for tokens.
5. Tokens are refreshed automatically before they expire.
"""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
import time
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx

from harbor.db import OAuthToken, session_scope, utcnow

TIMEOUT = 20


class OAuthError(RuntimeError):
    pass


def _origin(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"


def _path(url: str) -> str:
    p = urlparse(url).path.rstrip("/")
    return p


def parse_www_authenticate(header: str) -> dict[str, str]:
    return {k.lower(): v for k, v in re.findall(r'(\w+)="([^"]*)"', header or "")}


async def _get_json(client: httpx.AsyncClient, url: str) -> dict | None:
    try:
        r = await client.get(url, headers={"Accept": "application/json"})
    except httpx.HTTPError:
        return None
    if r.status_code != 200:
        return None
    try:
        return r.json()
    except ValueError:
        return None


async def probe(server_url: str, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str]]:
    """Send a bare initialize request; return (status, parsed WWW-Authenticate)."""
    body = {
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "harbor", "version": "1"},
        },
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.post(
                server_url,
                json=body,
                headers={"Accept": "application/json, text/event-stream", **(headers or {})},
            )
        except httpx.HTTPError:
            return 0, {}
    return r.status_code, parse_www_authenticate(r.headers.get("www-authenticate", ""))


async def discover(server_url: str) -> dict[str, Any]:
    """Return authorization-server metadata for an MCP server URL."""
    _, www = await probe(server_url)
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        prm = None
        candidates = []
        if www.get("resource_metadata"):
            candidates.append(www["resource_metadata"])
        origin, path = _origin(server_url), _path(server_url)
        if path:
            candidates.append(f"{origin}/.well-known/oauth-protected-resource{path}")
        candidates.append(f"{origin}/.well-known/oauth-protected-resource")
        for url in candidates:
            prm = await _get_json(client, url)
            if prm:
                break
        issuer = (prm or {}).get("authorization_servers", [origin])[0]
        iorigin, ipath = _origin(issuer), _path(issuer)
        meta_urls = []
        if ipath:
            meta_urls += [
                f"{iorigin}/.well-known/oauth-authorization-server{ipath}",
                f"{iorigin}/.well-known/openid-configuration{ipath}",
                f"{issuer.rstrip('/')}/.well-known/openid-configuration",
            ]
        meta_urls += [
            f"{iorigin}/.well-known/oauth-authorization-server",
            f"{iorigin}/.well-known/openid-configuration",
        ]
        meta = None
        for url in meta_urls:
            meta = await _get_json(client, url)
            if meta:
                break
        if not meta:
            meta = {
                "issuer": issuer,
                "authorization_endpoint": f"{iorigin}/authorize",
                "token_endpoint": f"{iorigin}/token",
                "registration_endpoint": f"{iorigin}/register",
            }
        meta["_resource"] = (prm or {}).get("resource") or server_url
        if prm and prm.get("scopes_supported") and not meta.get("scopes_supported"):
            meta["scopes_supported"] = prm["scopes_supported"]
        return meta


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def _row(db, user_id: int, name: str) -> OAuthToken | None:
    return db.query(OAuthToken).filter_by(user_id=user_id, server_name=name).one_or_none()


async def start(user_id: int, name: str, server_url: str, oauth_cfg: dict, redirect_uri: str) -> str:
    meta = await discover(server_url)
    with session_scope() as db:
        row = _row(db, user_id, name)
        if row is None:
            row = OAuthToken(user_id=user_id, server_name=name, server_url=server_url)
            db.add(row)
        client_info = row.get("client_json") if row.server_url == server_url else {}
        if oauth_cfg.get("client_id"):
            client_info = {
                "client_id": oauth_cfg["client_id"],
                "client_secret": oauth_cfg.get("client_secret", ""),
            }
        elif not client_info.get("client_id") or redirect_uri not in client_info.get("redirect_uris", []):
            reg = meta.get("registration_endpoint")
            if not reg:
                raise OAuthError(
                    "This server does not support automatic sign-up. "
                    "Add an oauth.client_id to its configuration."
                )
            async with httpx.AsyncClient(timeout=TIMEOUT) as client:
                r = await client.post(
                    reg,
                    json={
                        "client_name": "Harbor",
                        "redirect_uris": [redirect_uri],
                        "grant_types": ["authorization_code", "refresh_token"],
                        "response_types": ["code"],
                        "token_endpoint_auth_method": "none",
                    },
                )
            if r.status_code >= 400:
                raise OAuthError(f"Client registration failed ({r.status_code}): {r.text[:300]}")
            client_info = r.json()
            client_info.setdefault("redirect_uris", [redirect_uri])
        verifier, challenge = _pkce()
        state = secrets.token_urlsafe(24)
        row.server_url = server_url
        row.put("metadata_json", meta)
        row.put("client_json", {**client_info, "redirect_uri": redirect_uri})
        row.pending_state = state
        row.pending_verifier = verifier
        row.updated_at = utcnow()

    params = {
        "response_type": "code",
        "client_id": client_info["client_id"],
        "redirect_uri": redirect_uri,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "state": state,
        "resource": meta["_resource"],
    }
    scopes = oauth_cfg.get("scopes") or meta.get("scopes_supported")
    if scopes:
        params["scope"] = " ".join(scopes) if isinstance(scopes, list) else str(scopes)
    sep = "&" if "?" in meta["authorization_endpoint"] else "?"
    return f"{meta['authorization_endpoint']}{sep}{urlencode(params)}"


async def _token_request(meta: dict, client_info: dict, data: dict) -> dict:
    data = {**data, "client_id": client_info["client_id"]}
    auth = None
    if client_info.get("client_secret"):
        auth = (client_info["client_id"], client_info["client_secret"])
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        r = await client.post(
            meta["token_endpoint"], data=data, auth=auth, headers={"Accept": "application/json"}
        )
    if r.status_code >= 400:
        raise OAuthError(f"Token request failed ({r.status_code}): {r.text[:300]}")
    tokens = r.json()
    if "access_token" not in tokens:
        raise OAuthError("Token response had no access_token")
    if tokens.get("expires_in"):
        tokens["expires_at"] = time.time() + float(tokens["expires_in"])
    return tokens


async def complete(user_id: int, state: str, code: str) -> str:
    """Finish the flow. Returns the server name."""
    with session_scope() as db:
        row = db.query(OAuthToken).filter_by(user_id=user_id, pending_state=state).one_or_none()
        if row is None:
            raise OAuthError("This sign-in link is invalid or has expired. Please try again.")
        meta, client_info, verifier, name = (
            row.get("metadata_json"),
            row.get("client_json"),
            row.pending_verifier,
            row.server_name,
        )
    tokens = await _token_request(
        meta,
        client_info,
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": client_info["redirect_uri"],
            "code_verifier": verifier,
            "resource": meta["_resource"],
        },
    )
    with session_scope() as db:
        row = db.query(OAuthToken).filter_by(user_id=user_id, pending_state=state).one()
        row.put("tokens_json", tokens)
        row.pending_state = None
        row.pending_verifier = None
        row.updated_at = utcnow()
    return name


async def access_token(user_id: int, name: str, server_url: str) -> str | None:
    """Return a valid access token for the server, refreshing it when needed."""
    with session_scope() as db:
        row = _row(db, user_id, name)
        if row is None or row.server_url != server_url:
            return None
        tokens, meta, client_info = row.get("tokens_json"), row.get("metadata_json"), row.get("client_json")
    if not tokens.get("access_token"):
        return None
    if tokens.get("expires_at") and tokens["expires_at"] - 60 < time.time():
        if not tokens.get("refresh_token"):
            return None
        try:
            new = await _token_request(
                meta,
                client_info,
                {
                    "grant_type": "refresh_token",
                    "refresh_token": tokens["refresh_token"],
                    "resource": meta["_resource"],
                },
            )
        except OAuthError:
            return None
        new.setdefault("refresh_token", tokens["refresh_token"])
        with session_scope() as db:
            row = _row(db, user_id, name)
            if row:
                row.put("tokens_json", new)
                row.updated_at = utcnow()
        tokens = new
    return tokens["access_token"]


def has_tokens(user_id: int, name: str) -> bool:
    with session_scope() as db:
        row = _row(db, user_id, name)
        return bool(row and row.get("tokens_json").get("access_token"))


def forget(user_id: int, name: str) -> None:
    with session_scope() as db:
        row = _row(db, user_id, name)
        if row:
            db.delete(row)
