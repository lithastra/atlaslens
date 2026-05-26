import asyncio
import time


class RateBudget:
    """Per-source request budget with sliding-window rate limiting."""

    def __init__(
        self,
        max_requests_per_minute: int = 10,
        max_requests_per_cycle: int = 500,
    ) -> None:
        self._rpm = max_requests_per_minute
        self._max_cycle = max_requests_per_cycle
        self._cycle_count = 0
        self._timestamps: list[float] = []

    @property
    def remaining(self) -> int:
        return self._max_cycle - self._cycle_count

    async def acquire(self) -> None:
        if self._cycle_count >= self._max_cycle:
            raise BudgetExhausted(
                f"Cycle budget exhausted ({self._max_cycle} requests)"
            )

        now = time.monotonic()
        cutoff = now - 60.0
        self._timestamps = [t for t in self._timestamps if t > cutoff]

        if len(self._timestamps) >= self._rpm:
            wait = self._timestamps[0] - cutoff
            await asyncio.sleep(wait)
            self._timestamps = [
                t for t in self._timestamps if t > time.monotonic() - 60.0
            ]

        self._timestamps.append(time.monotonic())
        self._cycle_count += 1

    def reset_cycle(self) -> None:
        self._cycle_count = 0


class BudgetExhausted(Exception):
    pass
