"""
System health monitor — tracks server-side error rates and applies
concurrency throttling + cooldown when the target API is struggling.

Thresholds (conservative defaults):
  - 3+ consecutive 5xx → trigger cooldown
  - Response time > 10s → count as slow
  - Cooldown pause: 5 seconds
  - After cooldown: halve concurrency and double inter-request delay

All state is per-run (not global).
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_5XX_THRESHOLD = 3          # consecutive 5xx before cooldown
_SLOW_THRESHOLD_MS = 10_000 # ms
_COOLDOWN_SECS = 5.0        # pause duration
_MIN_DELAY_MS = 100         # minimum inter-request delay
_MAX_DELAY_MS = 2_000       # cap on adaptive delay


@dataclass
class HealthMonitor:
    """Tracks runtime health metrics and adapts execution parameters."""

    # Current execution parameters (mutable)
    concurrency: int = 3        # max parallel requests
    delay_ms: int = 300         # inter-request delay

    # Counters (reset/updated during run)
    _consecutive_5xx: int = field(default=0, repr=False)
    _timeouts: int = field(default=0, repr=False)
    _total_requests: int = field(default=0, repr=False)
    _in_cooldown: bool = field(default=False, repr=False)
    _last_cooldown: float = field(default=0.0, repr=False)

    def record(self, status_code: int, elapsed_ms: int) -> None:
        """Call after every HTTP response."""
        self._total_requests += 1

        if status_code >= 500:
            self._consecutive_5xx += 1
        else:
            self._consecutive_5xx = 0  # reset on any non-5xx

        if elapsed_ms > _SLOW_THRESHOLD_MS:
            self._timeouts += 1

    def record_error(self) -> None:
        """Call when a request raised an exception (connection error, timeout)."""
        self._consecutive_5xx += 1
        self._timeouts += 1
        self._total_requests += 1

    @property
    def is_overloaded(self) -> bool:
        return self._consecutive_5xx >= _5XX_THRESHOLD

    async def maybe_throttle(self) -> None:
        """
        If the server looks overloaded:
          - Trigger a cooldown pause
          - Halve concurrency (floor 1)
          - Double the inter-request delay (cap at _MAX_DELAY_MS)
        """
        if not self.is_overloaded:
            return

        now = time.monotonic()
        if self._in_cooldown and (now - self._last_cooldown) < _COOLDOWN_SECS:
            return  # already cooling down

        self._in_cooldown = True
        self._last_cooldown = now

        # Adapt parameters
        self.concurrency = max(1, self.concurrency // 2)
        self.delay_ms = min(_MAX_DELAY_MS, self.delay_ms * 2)
        self._consecutive_5xx = 0  # reset after adaptation

        logger.warning(
            "[HealthMonitor] Server overload detected — cooldown %.1fs, "
            "concurrency→%d, delay→%dms",
            _COOLDOWN_SECS, self.concurrency, self.delay_ms,
        )
        await asyncio.sleep(_COOLDOWN_SECS)
        self._in_cooldown = False

    def summary(self) -> dict:
        return {
            "total_requests": self._total_requests,
            "consecutive_5xx": self._consecutive_5xx,
            "timeouts": self._timeouts,
            "current_concurrency": self.concurrency,
            "current_delay_ms": self.delay_ms,
        }
