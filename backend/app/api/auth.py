"""Optional learner accounts: email + password, with progress carried over from the browser."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.api.deps import Database, find_anonymous_identity, find_session
from app.api.schemas import LoginRequest, MeResponse, RegisterRequest, UserResponse
from app.models import AnonymousIdentity, AuthSession, User
from app.security import (
    LEARNER_COOKIE,
    SESSION_COOKIE,
    burn_password_check,
    hash_password,
    hash_token,
    needs_rehash,
    new_session_token,
    secure_cookie,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])

_TOO_MANY = "Thử lại sau 5 phút."


def _client_key(request: Request) -> str:
    return hash_token(request.client.host if request.client else "unknown")


def _start_session(request: Request, response: Response, db: Database, user: User) -> None:
    """Replace any previous login session of this browser with a new one for ``user``."""
    settings = request.app.state.settings
    now = datetime.now(UTC)
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
    old_token = request.cookies.get(SESSION_COOKIE)
    if old_token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(old_token)))
    token = new_session_token()
    db.add(
        AuthSession(
            token_hash=hash_token(token),
            user_id=user.id,
            created_at=now,
            expires_at=now + timedelta(days=settings.session_days),
            last_used_at=now,
        )
    )
    db.commit()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_days * 24 * 60 * 60,
        httponly=True,
        secure=secure_cookie(request),
        samesite="lax",
        path="/",
    )


@router.post("/register", status_code=201)
def register(
    body: RegisterRequest, request: Request, response: Response, db: Database
) -> UserResponse:
    settings = request.app.state.settings
    if not settings.allow_registration:
        raise HTTPException(status_code=403, detail="Đăng ký tài khoản đang đóng.")
    if settings.registration_code and not secrets.compare_digest(
        (body.registration_code or "").encode(), settings.registration_code.encode()
    ):
        raise HTTPException(status_code=403, detail="Mã đăng ký không đúng.")
    # Every attempt counts, so a script cannot probe which emails exist or flood the table.
    limiter = request.app.state.register_limiter
    key = _client_key(request)
    if limiter.is_blocked(key):
        raise HTTPException(status_code=429, detail=_TOO_MANY)
    limiter.record_failure(key)

    if db.scalar(select(User.id).where(User.email == body.email)) is not None:
        raise HTTPException(status_code=409, detail="Email này đã được đăng ký.")

    display_name = body.display_name or body.email.split("@", 1)[0][:64]
    password_hash = hash_password(body.password)
    identity = find_anonymous_identity(db, request.cookies.get(LEARNER_COOKIE))
    anonymous = db.get(User, identity.user_id) if identity is not None else None
    try:
        if identity is not None and anonymous is not None and anonymous.email is None:
            # Convert this browser's user in place so its progress and history stay attached.
            user = anonymous
            user.email = body.email
            user.password_hash = password_hash
            user.display_name = display_name
            user.username = f"u-{secrets.token_hex(8)}"
            # The cookie must stop working: otherwise it would still open this account
            # after the learner logs out, without the password.
            db.execute(delete(AnonymousIdentity).where(AnonymousIdentity.id == identity.id))
        else:
            user = User(
                username=f"u-{secrets.token_hex(8)}",
                email=body.email,
                password_hash=password_hash,
                display_name=display_name,
                created_at=datetime.now(UTC),
            )
            db.add(user)
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email này đã được đăng ký.") from None

    _start_session(request, response, db, user)
    if identity is not None:
        response.delete_cookie(LEARNER_COOKIE, path="/", httponly=True, samesite="lax")
    return UserResponse.model_validate({"user": user})


@router.post("/login")
def login(
    body: LoginRequest, request: Request, response: Response, db: Database
) -> UserResponse:
    limiter = request.app.state.login_limiter
    key = _client_key(request)
    if limiter.is_blocked(key):
        raise HTTPException(status_code=429, detail=_TOO_MANY)
    user = db.scalar(select(User).where(User.email == body.email))
    if user is None:
        burn_password_check(body.password)
        ok = False
    else:
        ok = verify_password(user.password_hash, body.password)
    if user is None or not ok:
        limiter.record_failure(key)
        code = 429 if limiter.is_blocked(key) else 401
        detail = _TOO_MANY if code == 429 else "Email hoặc mật khẩu không đúng."
        raise HTTPException(status_code=code, detail=detail)
    limiter.reset(key)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    # The browser's anonymous progress is not merged; it stays under its own cookie.
    _start_session(request, response, db, user)
    return UserResponse.model_validate({"user": user})


@router.post("/logout", status_code=204)
def logout(
    db: Database,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> Response:
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == hash_token(token)))
        db.commit()
    response = Response(status_code=204)
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax")
    return response


@router.get("/me")
def me(
    db: Database,
    token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> MeResponse:
    """The signed-in account, or ``{"user": null}``. Never creates an anonymous identity."""
    session = find_session(db, token)
    return MeResponse.model_validate({"user": session.user if session else None})
