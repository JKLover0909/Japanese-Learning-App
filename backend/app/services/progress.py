"""Update an item's progress after an answer (rules in docs/architecture.md)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ItemProgress

MAX_WEAKNESS = 10
WRONG_PENALTY = 2
CORRECT_RELIEF = 1
MASTERED_STREAK = 3


@dataclass(frozen=True)
class ProgressState:
    seen_count: int = 0
    correct_count: int = 0
    wrong_count: int = 0
    weakness: int = 0
    streak: int = 0
    last_seen_at: datetime | None = None
    last_wrong_at: datetime | None = None


def apply_answer(state: ProgressState, is_correct: bool, now: datetime) -> ProgressState:
    """Pure progress rule: one wrong answer needs two correct answers to clear."""
    if is_correct:
        return ProgressState(
            seen_count=state.seen_count + 1,
            correct_count=state.correct_count + 1,
            wrong_count=state.wrong_count,
            weakness=max(0, state.weakness - CORRECT_RELIEF),
            streak=state.streak + 1,
            last_seen_at=now,
            last_wrong_at=state.last_wrong_at,
        )
    return ProgressState(
        seen_count=state.seen_count + 1,
        correct_count=state.correct_count,
        wrong_count=state.wrong_count + 1,
        weakness=min(MAX_WEAKNESS, state.weakness + WRONG_PENALTY),
        streak=0,
        last_seen_at=now,
        last_wrong_at=now,
    )


def is_weak(weakness: int) -> bool:
    return weakness > 0


def is_mastered(weakness: int, streak: int) -> bool:
    return weakness == 0 and streak >= MASTERED_STREAK


def focus_items(items, progress_by_item_id: dict[int, ItemProgress], limit: int = 5):
    """Return the strongest weak items in stable priority order."""
    weak = [
        item
        for item in items
        if progress_by_item_id.get(item.id) and progress_by_item_id[item.id].weakness > 0
    ]
    weak.sort(
        key=lambda item: (
            -progress_by_item_id[item.id].weakness,
            -(
                progress_by_item_id[item.id].last_wrong_at.timestamp()
                if progress_by_item_id[item.id].last_wrong_at
                else 0
            ),
            item.position,
        )
    )
    return weak[:limit]


def _state_of(row: ItemProgress) -> ProgressState:
    return ProgressState(
        seen_count=row.seen_count,
        correct_count=row.correct_count,
        wrong_count=row.wrong_count,
        weakness=row.weakness,
        streak=row.streak,
        last_seen_at=row.last_seen_at,
        last_wrong_at=row.last_wrong_at,
    )


def record_answer(
    db: Session, *, user_id: int, item_id: int, is_correct: bool, now: datetime
) -> ItemProgress:
    """Apply the rule to the user's ItemProgress row (created when missing). No commit."""
    row = db.execute(
        select(ItemProgress).where(ItemProgress.user_id == user_id, ItemProgress.item_id == item_id)
    ).scalar_one_or_none()
    if row is None:
        row = ItemProgress(user_id=user_id, item_id=item_id)
        db.add(row)
        state = ProgressState()
    else:
        state = _state_of(row)
    new = apply_answer(state, is_correct, now)
    row.seen_count = new.seen_count
    row.correct_count = new.correct_count
    row.wrong_count = new.wrong_count
    row.weakness = new.weakness
    row.streak = new.streak
    row.last_seen_at = new.last_seen_at
    row.last_wrong_at = new.last_wrong_at
    db.flush()
    return row
