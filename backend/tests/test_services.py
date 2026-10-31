import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.services.progress import ProgressState, apply_answer, is_mastered
from app.services.selection import select_questions


@dataclass
class Item:
    id: int


@dataclass
class Progress:
    weakness: int = 0
    seen_count: int = 0
    last_seen_at: datetime | None = None
    last_wrong_at: datetime | None = None


def test_progress_rule_and_mastery() -> None:
    now = datetime.now(UTC)
    state = apply_answer(ProgressState(), False, now)
    assert (state.seen_count, state.wrong_count, state.weakness, state.streak) == (1, 1, 2, 0)
    state = apply_answer(state, True, now + timedelta(seconds=1))
    assert state.weakness == 1
    state = apply_answer(state, True, now + timedelta(seconds=2))
    assert state.weakness == 0
    assert not is_mastered(state.weakness, state.streak)
    state = apply_answer(state, True, now + timedelta(seconds=3))
    assert is_mastered(state.weakness, state.streak)


def test_selection_small_lesson_and_focus_priority() -> None:
    items = [Item(i) for i in range(7)]
    now = datetime.now(UTC)
    progress = {
        0: Progress(weakness=2, last_wrong_at=now - timedelta(days=2)),
        1: Progress(weakness=2, last_wrong_at=now),
        2: Progress(weakness=1, last_wrong_at=now),
    }
    chosen = select_questions(items, progress, random.Random(12), session_size=20, focus_size=5)
    assert len(chosen) == 7
    assert len({question.item.id for question in chosen}) == 7
    assert {question.item.id for question in chosen if question.is_focus} == {0, 1, 2}


def test_selection_seeded_and_never_seen_before_seen() -> None:
    items = [Item(i) for i in range(100)]
    progress = {i: Progress(seen_count=5) for i in range(50)}
    one = select_questions(items, progress, random.Random(7))
    two = select_questions(items, progress, random.Random(7))
    assert [(q.item.id, q.is_focus) for q in one] == [(q.item.id, q.is_focus) for q in two]
    assert len(one) == 20
    # Never-seen items are ordered first; the first 60-item pool can also include
    # some seen items when 20 questions are drawn from it.
    assert sum(q.item.id >= 50 for q in one) >= 10
