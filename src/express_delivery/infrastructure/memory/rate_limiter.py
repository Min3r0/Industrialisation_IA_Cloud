"""Limitation du débit en mémoire, par fenêtre glissante (ADR-0005).

Compteur propre à chaque instance : c'est une défense en profondeur. La limite
globale (toutes instances confondues) est appliquée par Azure API Management.
"""
from __future__ import annotations

import math
import threading
import time
from collections import defaultdict, deque
from typing import Callable

from express_delivery.abstractions.rate_limiter import RateLimiter


class SlidingWindowRateLimiter(RateLimiter):
    def __init__(self, max_requests: int, window_seconds: float = 60.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        if max_requests < 1:
            raise ValueError("max_requests doit être >= 1.")
        self._max_requests = max_requests
        self._window = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def retry_after(self, identity: str) -> int:
        now = self._clock()
        with self._lock:
            hits = self._hits[identity]
            while hits and hits[0] <= now - self._window:
                hits.popleft()
            if len(hits) >= self._max_requests:
                return max(1, math.ceil(hits[0] + self._window - now))
            hits.append(now)
            return 0
