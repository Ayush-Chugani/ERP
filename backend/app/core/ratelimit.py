"""Rate limiting.

* ``db_hit`` – shared fixed-window counter in PostgreSQL. Used for credential endpoints, where the limit must hold
  across every API replica.
* ``LocalLimiter`` – in-process sliding window for the cheap global per-client limit.
"""
import time
from collections import defaultdict, deque
from threading import Lock

from sqlalchemy import text

from app.core.errors import Throttled
from app.db.session import db_session


def parse_rate(spec: str) -> tuple[int, int]:
    count, seconds = spec.split("/")
    return int(count), int(seconds)


def db_hit(bucket: str, spec: str) -> None:
    """Count a hit in its own short transaction (so rejected requests still count) and raise when over the limit."""
    limit, window = parse_rate(spec)
    start = int(time.time()) // window * window
    with db_session() as db:
        hits = db.execute(text(
            "INSERT INTO rate_limit_bucket (bucket, window_start, hits) VALUES (:b, :w, 1) "
            "ON CONFLICT (bucket, window_start) DO UPDATE SET hits = rate_limit_bucket.hits + 1 RETURNING hits"),
            {"b": bucket[:160], "w": start}).scalar_one()
    if hits > limit:
        raise Throttled("Too many attempts. Please wait and try again.", details={"retry_after": start + window - int(time.time())})


class LocalLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._last_sweep = time.monotonic()

    def hit(self, key: str, spec: str) -> None:
        limit, window = parse_rate(spec)
        now = time.monotonic()
        with self._lock:
            q = self._hits[key]
            while q and q[0] <= now - window:
                q.popleft()
            if len(q) >= limit:
                raise Throttled("Rate limit exceeded. Slow down and retry shortly.",
                                details={"retry_after": int(window - (now - q[0])) + 1})
            q.append(now)
            if now - self._last_sweep > 300:
                self._last_sweep = now
                for k in [k for k, v in self._hits.items() if not v or v[-1] <= now - window]:
                    del self._hits[k]


local_limiter = LocalLimiter()
