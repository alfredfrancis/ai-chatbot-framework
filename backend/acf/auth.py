"""Email + password accounts with cookie sessions. Standard library crypto only."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from acf.db import AuthSession, User, get_db, utcnow

COOKIE = "acf_session"
SESSION_DAYS = 30


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), n=2**14, r=8, p=1)
    return hmac.compare_digest(digest.hex(), digest_hex)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    db.add(
        AuthSession(
            token_hash=_token_hash(token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(days=SESSION_DAYS),
        )
    )
    return token


def delete_session(db: Session, token: str) -> None:
    row = db.get(AuthSession, _token_hash(token))
    if row:
        db.delete(row)


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE)
    if not token:
        auth = request.headers.get("authorization", "")
        if auth.lower().startswith("bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(401, "Not signed in")
    row = db.get(AuthSession, _token_hash(token))
    if not row or row.expires_at < utcnow():
        raise HTTPException(401, "Session expired")
    user = db.get(User, row.user_id)
    if not user:
        raise HTTPException(401, "Not signed in")
    return user
