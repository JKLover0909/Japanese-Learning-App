"""Choose the questions for a practice session.

Pure functions over ``(items, progress_by_item_id, rng)``: no database access, so the
result is deterministic under a seeded ``random.Random``. See docs/architecture.md,
"Session selection".
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Generic, Protocol, TypeVar

SESSION_SIZE = 20
FOCUS_SIZE = 5
MIN_GENERAL_POOL = 45
POOL_FACTOR = 3


class SelectableItem(Protocol):
    @property
    def id(self) -> int: ...


class ProgressLike(Protocol):
    @property
    def seen_count(self) -> int: ...
    @property
    def weakness(self) -> int: ...
    @property
    def last_seen_at(self) -> datetime | None: ...
    @property
    def last_wrong_at(self) -> datetime | None: ...


ItemT = TypeVar("ItemT", bound=SelectableItem)


@dataclass(frozen=True)
class SelectedQuestion(Generic[ItemT]):  # noqa: UP046 (Python 3.11 support)
    position: int
    item: ItemT
    is_focus: bool


def _timestamp(value: datetime | None) -> float | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.timestamp()


def focus_items(
    items: Sequence[ItemT],
    progress_by_item_id: Mapping[int, ProgressLike],
    focus_size: int = FOCUS_SIZE,
) -> list[ItemT]:
    """Weak items, weakest first, then most recently missed; at most ``focus_size``."""

    def sort_key(item: ItemT) -> tuple[int, float]:
        progress = progress_by_item_id[item.id]
        last_wrong = _timestamp(progress.last_wrong_at)
        return (-progress.weakness, -last_wrong if last_wrong is not None else math.inf)

    weak = [
        item
        for item in items
        if (progress := progress_by_item_id.get(item.id)) is not None and progress.weakness > 0
    ]
    weak.sort(key=sort_key)  # stable: equal keys keep content order
    return weak[: max(0, focus_size)]


def select_questions(
    items: Sequence[ItemT],
    progress_by_item_id: Mapping[int, ProgressLike],
    rng: random.Random,
    *,
    session_size: int = SESSION_SIZE,
    focus_size: int = FOCUS_SIZE,
) -> list[SelectedQuestion[ItemT]]:
    """Pick up to ``session_size`` items: weak ones first, then rarely seen ones."""
    session_size = max(0, session_size)
    focus = focus_items(items, progress_by_item_id, min(focus_size, session_size))
    focus_ids = {item.id for item in focus}

    general = [item for item in items if item.id not in focus_ids]
    needed = min(session_size - len(focus), len(general))
    chosen: list[ItemT] = []
    if needed > 0:
        # Random tie-break: shuffle first, then a stable sort on (seen_count, last_seen_at).
        rng.shuffle(general)

        def sort_key(item: ItemT) -> tuple[int, float]:
            progress = progress_by_item_id.get(item.id)
            if progress is None:
                return (0, -math.inf)
            last_seen = _timestamp(progress.last_seen_at)
            return (
                progress.seen_count,
                last_seen if last_seen is not None else -math.inf,
            )

        general.sort(key=sort_key)
        pool = general[: max(POOL_FACTOR * needed, MIN_GENERAL_POOL)]
        chosen = rng.sample(pool, needed)

    combined = [(item, True) for item in focus] + [(item, False) for item in chosen]
    rng.shuffle(combined)
    return [
        SelectedQuestion(position=index, item=item, is_focus=is_focus)
        for index, (item, is_focus) in enumerate(combined)
    ]
