"""Browser-scoped learner identity and shared database dependency."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Cookie, Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import AnonymousIdentity, AuthSession, User, Visit
from app.security import (
    LEARNER_COOKIE,
    SESSION_COOKIE,
    hash_token,
    new_session_token,
    secure_cookie,
)

Database = Annotated[Session, Depends(get_db)]

_SESSION_TOUCH_INTERVAL = timedelta(hours=1)


def find_session(db: Session, token: str | None) -> AuthSession | None:
    """The unexpired login session for a ``jp_session`` cookie value, if any."""
    if not token or len(token) > 128:
        return None
    return db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_token(token),
            AuthSession.expires_at > datetime.now(UTC),
        )
    )


def find_anonymous_identity(db: Session, token: str | None) -> AnonymousIdentity | None:
    if not token or len(token) > 128:
        return None
    return db.scalar(
        select(AnonymousIdentity).where(AnonymousIdentity.token_hash == hash_token(token))
    )


def get_anonymous_user(
    request: Request,
    response: Response,
    db: Database,
    token: Annotated[str | None, Cookie(alias=LEARNER_COOKIE)] = None,
) -> User:
    """Each browser owns a separate user row; old account records remain untouched."""
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    identity = None
    if token and len(token) <= 128:
        identity = db.scalar(
            select(AnonymousIdentity).where(AnonymousIdentity.token_hash == hash_token(token))
        )
    if identity is None:
        token = new_session_token()
        user = User(
            username=f"anon-{hash_token(token)[:24]}",
            password_hash="!disabled",
            display_name="Người học",
            created_at=now,
        )
        db.add(user)
        db.flush()
        identity = AnonymousIdentity(
            token_hash=hash_token(token),
            user_id=user.id,
            created_at=now,
            last_seen_at=now,
        )
        db.add(identity)
        db.flush()
        db.add(Visit(identity_id=identity.id, visited_at=now))
        db.commit()
        response.set_cookie(
            LEARNER_COOKIE,
            token,
            max_age=365 * 24 * 60 * 60,
            httponly=True,
            secure=secure_cookie(request),
            samesite="lax",
            path="/",
        )
    elif identity.last_seen_at < now:
        # A visit means activity following >=30 minutes of inactivity, not every API call.
        previous = identity.last_seen_at
        won = db.execute(
            update(AnonymousIdentity)
            .where(AnonymousIdentity.id == identity.id, AnonymousIdentity.last_seen_at == previous)
            .values(last_seen_at=now)
        )
        if won.rowcount and previous <= now - timedelta(minutes=30):
            db.add(Visit(identity_id=identity.id, visited_at=now))
        db.commit()
    user = db.get(User, identity.user_id)
    assert user is not None
    return user


def get_current_user(
    request: Request,
    response: Response,
    db: Database,
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
    learner_token: Annotated[str | None, Cookie(alias=LEARNER_COOKIE)] = None,
) -> User:
    """A logged-in account when the session cookie is valid, otherwise the anonymous browser."""
    session = find_session(db, session_token)
    if session is not None:
        now = datetime.now(UTC)
        if session.last_used_at <= now - _SESSION_TOUCH_INTERVAL:
            session.last_used_at = now
            db.commit()
        return session.user
    return get_anonymous_user(request, response, db, learner_token)


CurrentLearner = Annotated[User, Depends(get_current_user)]
# Kept so the learner endpoints keep their name; they now accept either kind of learner.
AnonymousLearner = CurrentLearner
