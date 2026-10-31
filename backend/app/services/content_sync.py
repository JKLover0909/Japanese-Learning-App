"""Upsert validated lesson content into the database (by lesson slug and item key)."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.content.schema import LessonFile
from app.models import Item, Lesson


@dataclass
class SyncReport:
    lessons_created: int = 0
    lessons_updated: int = 0
    lessons_deactivated: int = 0
    items_created: int = 0
    items_updated: int = 0
    items_deactivated: int = 0


def content_hash(lesson: LessonFile) -> str:
    payload = json.dumps(lesson.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sync_content(db: Session, lessons: Sequence[LessonFile]) -> SyncReport:
    """Make the DB match ``lessons``. Removed items/lessons are deactivated, never deleted."""
    report = SyncReport()
    existing = {lesson.slug: lesson for lesson in db.scalars(select(Lesson))}
    incoming_slugs = {lesson.slug for lesson in lessons}

    # Positions are not unique in the DB, so lessons can swap positions freely.
    for lesson_file in lessons:
        digest = content_hash(lesson_file)
        row = existing.get(lesson_file.slug)
        if row is None:
            row = Lesson(slug=lesson_file.slug)
            db.add(row)
            report.lessons_created += 1
        elif row.content_hash == digest and row.is_active:
            continue
        else:
            report.lessons_updated += 1
        row.position = lesson_file.position
        row.title = lesson_file.title
        row.description = lesson_file.description
        row.content_hash = digest
        row.is_active = True
        db.flush()
        _move_legacy_items(db, row, lesson_file)
        _sync_items(db, row, lesson_file, report)

    for slug, row in existing.items():
        if slug not in incoming_slugs and row.is_active:
            row.is_active = False
            report.lessons_deactivated += 1
    db.commit()
    return report


def _move_legacy_items(db: Session, lesson: Lesson, lesson_file: LessonFile) -> None:
    """Move pre-split item rows so progress and session history keep their FK IDs."""
    if lesson_file.slug not in {"greetings", "numbers"}:
        return
    source = db.scalar(select(Lesson).where(Lesson.slug == "greetings-numbers"))
    if source is None or source.id == lesson.id:
        return
    source_items = {
        item.key: item for item in db.scalars(select(Item).where(Item.lesson_id == source.id))
    }
    incoming_keys = {item.key for item in lesson_file.items}
    for key in incoming_keys:
        row = source_items.get(key)
        if row is not None:
            row.lesson_id = lesson.id
    # Session factory uses autoflush=False: persist moves before querying target items.
    db.flush()


def _sync_items(db: Session, lesson: Lesson, lesson_file: LessonFile, report: SyncReport) -> None:
    items = {item.key: item for item in db.scalars(select(Item).where(Item.lesson_id == lesson.id))}
    incoming = set()
    for position, content in enumerate(lesson_file.items):
        incoming.add(content.key)
        values = {
            "prompt": content.prompt,
            "kind": content.kind,
            "meaning": content.meaning,
            "readings": list(content.readings),
            "tags": list(content.tags),
            "position": position,
            "is_active": True,
        }
        row = items.get(content.key)
        if row is None:
            db.add(Item(lesson_id=lesson.id, key=content.key, **values))
            report.items_created += 1
            continue
        if any(getattr(row, name) != value for name, value in values.items()):
            for name, value in values.items():
                setattr(row, name, value)
            report.items_updated += 1
    for key, row in items.items():
        if key not in incoming and row.is_active:
            row.is_active = False
            report.items_deactivated += 1
    db.flush()
