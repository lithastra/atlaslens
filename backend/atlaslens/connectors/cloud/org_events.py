import asyncio
import logging
from datetime import datetime

import httpx

from atlaslens.connectors.base import Cursor, RawEvent
from atlaslens.connectors.rate_budget import RateBudget
from atlaslens.models.event import Deployment, Product

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0
_PAGE_SIZE = 200


class OrgEventsConnector:
    """Polls the Atlassian Org events-stream API.

    Uses the polling API (/events-stream) rather than the advanced
    /events path per API_VERIFICATION.md — the advanced path is
    rate-limited to ~10 req/min and partially deprecates 30 Jun 2026.
    """

    product: Product = "jira"
    deployment: Deployment = "cloud"

    def __init__(
        self,
        org_id: str,
        api_key: str,
        client: httpx.AsyncClient,
        budget: RateBudget | None = None,
    ) -> None:
        self._org_id = org_id
        self._api_key = api_key
        self._client = client
        self._budget = budget

    async def fetch_audit(self, cursor: Cursor) -> list[RawEvent]:
        events: list[RawEvent] = []
        next_cursor = cursor

        while True:
            params: dict[str, str | int] = {"limit": _PAGE_SIZE}
            if next_cursor:
                params["cursor"] = next_cursor

            resp = await self._request(
                "GET",
                f"https://api.atlassian.com/admin/v1/orgs/"
                f"{self._org_id}/events-stream",
                params=params,
            )
            data = resp.json()
            items: list[dict] = data.get("data", [])  # type: ignore[type-arg]

            for item in items:
                attrs = item.get("attributes", {})
                events.append(
                    RawEvent(
                        source_id=item.get("id", ""),
                        occurred_at=_parse_date(
                            attrs.get("time", "")
                        ),
                        event_type=attrs.get("action", "unknown"),
                        payload=item,
                    )
                )

            meta = data.get("meta", {})
            new_cursor = meta.get("next_cursor")
            if not items or not new_cursor or new_cursor == next_cursor:
                break
            next_cursor = new_cursor

        logger.info(
            "org events-stream: fetched %d records", len(events)
        )
        return events

    async def fetch_activity(self, cursor: Cursor) -> list[RawEvent]:
        return []

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs: object,
    ) -> httpx.Response:
        if self._budget:
            await self._budget.acquire()
        headers = {"Authorization": f"Bearer {self._api_key}"}
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self._client.request(
                    method,
                    url,
                    headers=headers,
                    timeout=30.0,
                    **kwargs,  # type: ignore[arg-type]
                )
                if resp.status_code == 429:
                    wait = float(
                        resp.headers.get(
                            "Retry-After",
                            _BACKOFF_BASE ** (attempt + 1),
                        )
                    )
                    logger.warning(
                        "org-events: rate-limited, retrying in %.1fs",
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp
            except httpx.TimeoutException:
                if attempt == _MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(_BACKOFF_BASE ** (attempt + 1))
        raise RuntimeError("max retries exceeded")


def _parse_date(s: str) -> datetime:
    if not s:
        return datetime.now()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)
