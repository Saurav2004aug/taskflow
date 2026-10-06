"""
Token-bucket rate limiter, keyed by client (user id or IP address).

Each key gets a bucket holding up to `capacity` tokens that refills at
`refill_rate` tokens/second; a request spends one token. Bursts up to the
capacity are allowed, and the long-run rate is capped at refill_rate.

State is in-process memory: fine for a single instance. With several
replicas, the buckets would move to Redis (see the mini-redis project).
"""

import threading
import time
from typing import Callable


class RateLimiter:
    def __init__(self, capacity: int, refill_rate: float,
                 clock: Callable[[], float] = time.monotonic, max_keys: int = 100_000):
        if capacity <= 0 or refill_rate <= 0:
            raise ValueError("capacity and refill_rate must be positive")
        self.capacity = capacity
        self.refill_rate = refill_rate
        self._clock = clock
        self._max_keys = max_keys
        self._buckets: dict[str, list[float]] = {}  # key -> [tokens, last_refill]
        self._lock = threading.Lock()

    def check(self, key: str) -> tuple[bool, int, float]:
        """Spend one token. Returns (allowed, remaining, retry_after_seconds)."""
        now = self._clock()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                if len(self._buckets) >= self._max_keys:
                    self._evict_full_buckets(now)
                bucket = self._buckets[key] = [float(self.capacity), now]
            else:
                bucket[0] = min(self.capacity, bucket[0] + (now - bucket[1]) * self.refill_rate)
                bucket[1] = now
            if bucket[0] >= 1:
                bucket[0] -= 1
                return True, int(bucket[0]), 0.0
            return False, 0, (1 - bucket[0]) / self.refill_rate

    def _evict_full_buckets(self, now: float) -> None:
        """Bound memory: forget clients whose bucket has refilled completely
        (they're indistinguishable from brand-new clients anyway)."""
        full_after = self.capacity / self.refill_rate
        stale = [k for k, (_, last) in self._buckets.items() if now - last >= full_after]
        for k in stale:
            del self._buckets[k]
