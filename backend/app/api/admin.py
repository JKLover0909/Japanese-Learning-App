"""Independent admin authentication and aggregate usage only."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Cookie, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from app.api.deps import Database
from app.models import AdminSession, AnonymousIdentity, PracticeSession, SessionQuestion, Visit
from app.security import (
    ADMIN_COOKIE,
    hash_token,
    new_session_token,
    secure_cookie,
    verify_password,
)

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


def _require_admin(request: Request, db: Database, token: str | None) -> None:
    settings = request.app.state.settings
    if not settings.admin_username or not settings.admin_password_hash:
        raise HTTPException(status_code=401, detail="Quản trị chưa được cấu hình.")
    session = db.scalar(
        select(AdminSession).where(
            AdminSession.token_hash == hash_token(token or ""),
            AdminSession.expires_at > datetime.now(UTC),
        )
    )
    if session is None:
        raise HTTPException(status_code=401, detail="Vui lòng đăng nhập quản trị.")


@router.post("/login")
def admin_login(
    body: AdminLoginRequest, request: Request, response: Response, db: Database
) -> dict[str, str]:
    settings = request.app.state.settings
    limiter = request.app.state.admin_login_limiter
    # Username-independent bucket prevents bypass by rotating submitted names.
    key = hash_token(request.client.host if request.client else "unknown")
    if limiter.is_blocked(key):
        raise HTTPException(status_code=429, detail="Thử lại sau 5 phút.")
    if not settings.admin_username or not settings.admin_password_hash:
        raise HTTPException(status_code=503, detail="Quản trị chưa được cấu hình.")
    password_ok = verify_password(settings.admin_password_hash, body.password)
    username_ok = secrets.compare_digest(body.username.encode(), settings.admin_username.encode())
    if not password_ok or not username_ok:
        limiter.record_failure(key)
        code = 429 if limiter.is_blocked(key) else 401
        raise HTTPException(status_code=code, detail="Tên đăng nhập hoặc mật khẩu không đúng.")
    limiter.reset(key)
    now = datetime.now(UTC)
    db.execute(delete(AdminSession).where(AdminSession.expires_at <= now))
    old_token = request.cookies.get(ADMIN_COOKIE)
    if old_token:
        db.execute(delete(AdminSession).where(AdminSession.token_hash == hash_token(old_token)))
    token = new_session_token()
    db.add(AdminSession(token_hash=hash_token(token), expires_at=now + timedelta(hours=12)))
    db.commit()
    response.set_cookie(
        ADMIN_COOKIE,
        token,
        max_age=12 * 3600,
        httponly=True,
        secure=secure_cookie(request),
        samesite="strict",
        path="/api/admin",
    )
    return {"status": "ok"}


@router.post("/logout", status_code=204)
def admin_logout(
    response: Response,
    db: Database,
    token: Annotated[str | None, Cookie(alias=ADMIN_COOKIE)] = None,
) -> Response:
    if token:
        db.execute(delete(AdminSession).where(AdminSession.token_hash == hash_token(token)))
        db.commit()
    response.delete_cookie(ADMIN_COOKIE, path="/api/admin", httponly=True, samesite="strict")
    return response


@router.get("/overview")
def admin_overview(
    request: Request,
    db: Database,
    token: Annotated[str | None, Cookie(alias=ADMIN_COOKIE)] = None,
) -> dict[str, Any]:
    _require_admin(request, db, token)
    now = datetime.now(UTC)
    # Keep only 90 days of coarse visit events; identity/progress stays until explicitly removed.
    db.execute(delete(Visit).where(Visit.visited_at < now - timedelta(days=90)))
    db.commit()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=29)
    daily = dict(
        db.execute(
            select(func.date(Visit.visited_at), func.count(Visit.id))
            .where(Visit.visited_at >= start)
            .group_by(func.date(Visit.visited_at))
        ).all()
    )
    recent = now - timedelta(minutes=15)
    active_sessions = (
        select(SessionQuestion.session_id).where(SessionQuestion.answered_at >= recent).distinct()
    )
    return {
        "visitors_total": db.scalar(select(func.count(AnonymousIdentity.id))) or 0,
        "active_learners_7d": db.scalar(
            select(func.count(AnonymousIdentity.id)).where(
                AnonymousIdentity.last_seen_at >= now - timedelta(days=7)
            )
        )
        or 0,
        "active_sessions_15m": db.scalar(
            select(func.count(PracticeSession.id)).where(
                (PracticeSession.created_at >= recent) | PracticeSession.id.in_(active_sessions)
            )
        )
        or 0,
        "questions_in_sessions": db.scalar(select(func.sum(PracticeSession.total))) or 0,
        "answers_submitted": db.scalar(select(func.sum(PracticeSession.answered_count))) or 0,
        "visits_by_day": [
            {
                "date": (start + timedelta(days=i)).date().isoformat(),
                "visits": daily.get((start + timedelta(days=i)).date().isoformat(), 0),
            }
            for i in range(30)
        ],
    }
