"""Lesson catalog, details and per-user progress reset."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import func, select, update

from app.api.deps import AnonymousLearner, Database
from app.api.schemas import (
    ItemProgressOut,
    LessonDetailOut,
    LessonItemOut,
    LessonListResponse,
    LessonProgressOut,
    LessonSummaryOut,
)
from app.models import (
    SESSION_ABANDONED,
    SESSION_ACTIVE,
    Item,
    ItemProgress,
    Lesson,
    PracticeSession,
)
from app.services.progress import is_mastered
from app.services.romaji import romaji_options

router = APIRouter(prefix="/lessons", tags=["lessons"])


def _progress_out(row: ItemProgress) -> ItemProgressOut:
    return ItemProgressOut(
        seen_count=row.seen_count,
        correct_count=row.correct_count,
        wrong_count=row.wrong_count,
        weakness=row.weakness,
        streak=row.streak,
        last_seen_at=row.last_seen_at,
    )


def _lesson_summary(db: Database, lesson: Lesson, user_id: int) -> LessonSummaryOut:
    item_rows = (
        db.execute(
            select(ItemProgress)
            .join(Item, Item.id == ItemProgress.item_id)
            .where(
                Item.lesson_id == lesson.id,
                Item.is_active.is_(True),
                ItemProgress.user_id == user_id,
            )
        )
        .scalars()
        .all()
    )
    active_items = (
        db.scalar(
            select(func.count(Item.id)).where(Item.lesson_id == lesson.id, Item.is_active.is_(True))
        )
        or 0
    )
    total_answers = sum(row.seen_count for row in item_rows)
    correct_answers = sum(row.correct_count for row in item_rows)
    progress = LessonProgressOut(
        seen_items=sum(row.seen_count > 0 for row in item_rows),
        weak_items=sum(row.weakness > 0 for row in item_rows),
        mastered_items=sum(is_mastered(row.weakness, row.streak) for row in item_rows),
        total_answers=total_answers,
        correct_answers=correct_answers,
        accuracy=correct_answers / total_answers if total_answers else None,
    )
    active_session_id = db.scalar(
        select(PracticeSession.id)
        .where(
            PracticeSession.user_id == user_id,
            PracticeSession.lesson_id == lesson.id,
            PracticeSession.status == SESSION_ACTIVE,
        )
        .order_by(PracticeSession.created_at.desc())
        .limit(1)
    )
    return LessonSummaryOut(
        slug=lesson.slug,
        position=lesson.position,
        title=lesson.title,
        description=lesson.description,
        item_count=active_items,
        progress=progress,
        active_session_id=active_session_id,
    )


@router.get("", response_model=LessonListResponse)
def list_lessons(db: Database, user: AnonymousLearner) -> dict[str, Any]:
    lessons = db.scalars(select(Lesson).where(Lesson.is_active.is_(True)).order_by(Lesson.position))
    return {"lessons": [_lesson_summary(db, lesson, user.id) for lesson in lessons]}


@router.get("/{slug}", response_model=LessonDetailOut)
def lesson_detail(slug: str, db: Database, user: AnonymousLearner) -> dict[str, Any]:
    lesson = db.scalar(select(Lesson).where(Lesson.slug == slug, Lesson.is_active.is_(True)))
    if lesson is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài học.")
    progress = {
        row.item_id: row
        for row in db.scalars(
            select(ItemProgress)
            .join(Item, Item.id == ItemProgress.item_id)
            .where(Item.lesson_id == lesson.id, ItemProgress.user_id == user.id)
        )
    }
    items = db.scalars(
        select(Item)
        .where(Item.lesson_id == lesson.id, Item.is_active.is_(True))
        .order_by(Item.position)
    )
    output = [
        LessonItemOut(
            key=item.key,
            prompt=item.prompt,
            kind=item.kind,
            meaning=item.meaning,
            tags=item.tags,
            readings=item.readings,
            romaji=romaji_options(item.readings),
            progress=_progress_out(progress[item.id]) if item.id in progress else None,
        )
        for item in items
    ]
    return {"lesson": _lesson_summary(db, lesson, user.id), "items": output}


@router.delete("/{slug}/progress", status_code=204)
def reset_progress(slug: str, db: Database, user: AnonymousLearner) -> Response:
    lesson = db.scalar(select(Lesson).where(Lesson.slug == slug, Lesson.is_active.is_(True)))
    if lesson is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài học.")
    db.execute(
        update(PracticeSession)
        .where(
            PracticeSession.user_id == user.id,
            PracticeSession.lesson_id == lesson.id,
            PracticeSession.status == SESSION_ACTIVE,
        )
        .values(status=SESSION_ABANDONED)
    )
    db.execute(
        ItemProgress.__table__.delete().where(
            ItemProgress.user_id == user.id,
            ItemProgress.item_id.in_(select(Item.id).where(Item.lesson_id == lesson.id)),
        )
    )
    db.commit()
    return Response(status_code=204)
