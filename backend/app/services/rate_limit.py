"""In-memory sliding-window limiter for failed logins (single-process server)."""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable, Hashable

LOGIN_MAX_FAILURES = 5
LOGIN_WINDOW_SECONDS = 5 * 60


class FailureLimiter:
    """Blocks a key after ``max_failures`` failures within ``window`` seconds."""

    def __init__(
        self,
        max_failures: int = LOGIN_MAX_FAILURES,
        window: float = LOGIN_WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.max_failures = max_failures
        self.window = window
        self._clock = clock
        self._failures: dict[Hashable, deque[float]] = {}
        self._lock = threading.Lock()

    def _prune(self, key: Hashable, now: float) -> deque[float] | None:
        entries = self._failures.get(key)
        if entries is None:
            return None
        while entries and now - entries[0] >= self.window:
            entries.popleft()
        if not entries:
            del self._failures[key]
            return None
        return entries

    def is_blocked(self, key: Hashable) -> bool:
        with self._lock:
            entries = self._prune(key, self._clock())
            return entries is not None and len(entries) >= self.max_failures

    def record_failure(self, key: Hashable) -> None:
        with self._lock:
            now = self._clock()
            entries = self._prune(key, now)
            if entries is None:
                entries = self._failures[key] = deque()
            entries.append(now)
            # Keep memory bounded: only the newest max_failures timestamps matter.
            while len(entries) > self.max_failures:
                entries.popleft()
            if len(self._failures) > 10_000:
                for stale in [k for k in self._failures if k != key]:
                    self._prune(stale, now)

    def reset(self, key: Hashable) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._failures.clear()
