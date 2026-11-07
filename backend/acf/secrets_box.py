"""Encryption at rest for secrets kept in the database: users' model API keys, MCP configurations (they
hold headers and environment variables with tokens) and OAuth client secrets and tokens.

AES-256-GCM with a key derived (HKDF-SHA256) from ACF_SECRET_KEY. Without one, a random key is created
once in <data dir>/secret.key: fine for a laptop, but in production set ACF_SECRET_KEY and keep it apart
from database backups — whoever has both can read the secrets. Values written before encryption existed
are read as they are and encrypted at startup (`db.encrypt_existing`).
"""

from __future__ import annotations

import base64
import logging
import os
import secrets
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from acf import config

PREFIX = "enc:v1:"
_AAD = b"acf-secret"
log = logging.getLogger("acf.secrets")


class SecretKeyError(RuntimeError):
    pass


def _secret() -> str:
    s = config.settings
    if s.secret_key:
        return s.secret_key
    path = s.data_dir / "secret.key"
    if not path.exists():
        log.warning("ACF_SECRET_KEY is not set: created %s. Set ACF_SECRET_KEY in production.", path)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(secrets.token_urlsafe(48))
    return path.read_text().strip()


@lru_cache(maxsize=4)
def _aead(secret: str) -> AESGCM:
    key = HKDF(algorithm=hashes.SHA256(), length=32, salt=b"acf", info=b"acf secrets v1").derive(secret.encode())
    return AESGCM(key)


def encrypt(text: str | None) -> str | None:
    if not text or text.startswith(PREFIX):
        return text
    nonce = os.urandom(12)
    data = _aead(_secret()).encrypt(nonce, text.encode(), _AAD)
    return PREFIX + base64.urlsafe_b64encode(nonce + data).decode()


def decrypt(value: str | None) -> str | None:
    if not value or not value.startswith(PREFIX):
        return value  # empty, or stored before encryption (encrypted at the next startup)
    raw = base64.urlsafe_b64decode(value[len(PREFIX) :])
    try:
        return _aead(_secret()).decrypt(raw[:12], raw[12:], _AAD).decode()
    except InvalidTag as e:
        raise SecretKeyError(
            "Stored secrets can't be decrypted: ACF_SECRET_KEY is not the key they were encrypted with."
        ) from e
