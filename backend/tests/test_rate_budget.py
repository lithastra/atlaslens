import pytest

from atlaslens.connectors.rate_budget import BudgetExhausted, RateBudget


class TestRateBudget:
    @pytest.mark.asyncio
    async def test_acquire_within_budget(self) -> None:
        budget = RateBudget(max_requests_per_minute=100, max_requests_per_cycle=5)
        for _ in range(5):
            await budget.acquire()
        assert budget.remaining == 0

    @pytest.mark.asyncio
    async def test_cycle_budget_exhausted(self) -> None:
        budget = RateBudget(max_requests_per_minute=100, max_requests_per_cycle=3)
        for _ in range(3):
            await budget.acquire()
        with pytest.raises(BudgetExhausted):
            await budget.acquire()

    @pytest.mark.asyncio
    async def test_reset_cycle(self) -> None:
        budget = RateBudget(max_requests_per_minute=100, max_requests_per_cycle=2)
        await budget.acquire()
        await budget.acquire()
        budget.reset_cycle()
        assert budget.remaining == 2
        await budget.acquire()

    @pytest.mark.asyncio
    async def test_remaining_tracks_correctly(self) -> None:
        budget = RateBudget(max_requests_per_minute=100, max_requests_per_cycle=10)
        assert budget.remaining == 10
        await budget.acquire()
        assert budget.remaining == 9
