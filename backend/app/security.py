"""Password hashing (argon2id) and opaque session tokens."""

from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Request

SESSION_COOKIE = "jp_session"
LEARNER_COOKIE = "jp_learner"
ADMIN_COOKIE = "jp_admin"
ADMIN_SESSION_COOKIE = ADMIN_COOKIE
CSRF_HEADER = "X-Requested-With"
CSRF_VALUE = "jp-practice"

_hasher = PasswordHasher()
# A valid hash of a random password, verified when the username does not exist so that
# login timing does not reveal which usernames are registered.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def secure_cookie(request: Request) -> bool:
    setting = request.app.state.settings.cookie_secure
    return request.url.scheme == "https" if setting == "auto" else setting == "true"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def burn_password_check(password: str) -> None:
    """Spend the same time as a real verification (unknown username)."""
    verify_password(_DUMMY_HASH, password)


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return False


def new_session_token() -> str:
    """32 random bytes, URL-safe. Only its SHA-256 hash is stored."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
