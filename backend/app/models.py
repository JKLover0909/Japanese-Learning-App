"""SQLAlchemy ORM models. ``alembic/versions`` must stay in sync with this file."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, utcnow

metadata: MetaData = Base.metadata

SESSION_ACTIVE = "active"
SESSION_COMPLETED = "completed"
SESSION_ABANDONED = "abandoned"


class UTCDateTime(TypeDecorator[datetime]):
    """Stores naive UTC (SQLite has no time zones) and always returns aware UTC."""

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is not None:
            value = value.astimezone(UTC).replace(tzinfo=None)
        return value

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(32), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class AnonymousIdentity(Base):
    __tablename__ = "anonymous_identities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    identity_id: Mapped[int] = mapped_column(
        ForeignKey("anonymous_identities.id", ondelete="CASCADE"), index=True
    )
    visited_at: Mapped[datetime] = mapped_column(UTCDateTime(), index=True)


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_used_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)

    user: Mapped[User] = relationship(lazy="joined")


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    position: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    """False when the lesson file disappeared from the content directory."""


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (UniqueConstraint("lesson_id", "key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(64))
    prompt: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))
    meaning: Mapped[str | None] = mapped_column(String(160))
    readings: Mapped[list[str]] = mapped_column(JSON)
    tags: Mapped[list[str]] = mapped_column(JSON)
    position: Mapped[int] = mapped_column(Integer)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class ItemProgress(Base):
    __tablename__ = "item_progress"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    item_id: Mapped[int] = mapped_column(
        ForeignKey("items.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    seen_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    weakness: Mapped[int] = mapped_column(Integer, default=0)
    streak: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    last_wrong_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class PracticeSession(Base):
    __tablename__ = "practice_sessions"
    __table_args__ = (
        Index("ix_practice_sessions_user_lesson_status", "user_id", "lesson_id", "status"),
        Index("ix_practice_sessions_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    lesson_id: Mapped[int] = mapped_column(ForeignKey("lessons.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(16), default=SESSION_ACTIVE)
    total: Mapped[int] = mapped_column(Integer)
    answered_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    focus_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    lesson: Mapped[Lesson] = relationship(lazy="joined")
    questions: Mapped[list[SessionQuestion]] = relationship(
        order_by="SessionQuestion.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="session",
    )


class SessionQuestion(Base):
    __tablename__ = "session_questions"
    __table_args__ = (UniqueConstraint("session_id", "position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("practice_sessions.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    is_focus: Mapped[bool] = mapped_column(Boolean, default=False)
    answer: Mapped[str | None] = mapped_column(String(200))
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    answered_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    session: Mapped[PracticeSession] = relationship(back_populates="questions")
    item: Mapped[Item] = relationship(lazy="joined")

class ChapterTest(Base):
    """One attempt at an end-of-chapter listening test."""

    __tablename__ = "chapter_tests"
    __table_args__ = (
        Index("ix_chapter_tests_user_chapter_created", "user_id", "chapter", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    chapter: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default=SESSION_ACTIVE)
    total: Mapped[int] = mapped_column(Integer)
    answered_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    questions: Mapped[list[ChapterTestQuestion]] = relationship(
        order_by="ChapterTestQuestion.position",
        cascade="all, delete-orphan",
        passive_deletes=True,
        back_populates="test",
    )

class ChapterTestQuestion(Base):
    __tablename__ = "chapter_test_questions"
    __table_args__ = (UniqueConstraint("test_id", "position"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    test_id: Mapped[str] = mapped_column(ForeignKey("chapter_tests.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    part: Mapped[str] = mapped_column(String(32))
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), index=True)
    options: Mapped[list[str]] = mapped_column(JSON)
    answer_index: Mapped[int] = mapped_column(Integer)
    choice: Mapped[int | None] = mapped_column(Integer)
    is_correct: Mapped[bool | None] = mapped_column(Boolean)
    answered_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    test: Mapped[ChapterTest] = relationship(back_populates="questions")
    item: Mapped[Item] = relationship(lazy="joined")
