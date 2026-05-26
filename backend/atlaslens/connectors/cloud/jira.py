import asyncio
import logging
from datetime import datetime
from typing import Any

import httpx

from atlaslens.connectors.base import Cursor, RawEvent
from atlaslens.connectors.rate_budget import RateBudget
from atlaslens.models.event import Deployment, Product

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0
_PAGE_LIMIT = 1000


class JiraCloudConnector:
    product: Product = "jira"
    deployment: Deployment = "cloud"

    def __init__(
        self,
        base_url: str,
        auth: tuple[str, str],
        client: httpx.AsyncClient,
        budget: RateBudget | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = auth
        self._client = client
        self._budget = budget

    async def fetch_audit(self, cursor: Cursor) -> list[RawEvent]:
        events: list[RawEvent] = []
        offset = 0

        while True:
            params: dict[str, str | int] = {
                "limit": _PAGE_LIMIT,
                "offset": offset,
            }
            if cursor:
                params["from"] = cursor

            resp = await self._request(
                "GET",
                f"{self._base_url}/rest/api/3/auditing/record",
                params=params,
            )
            data = resp.json()
            records: list[dict[str, Any]] = data.get("records", [])

            for record in records:
                events.append(
                    RawEvent(
                        source_id=str(record["id"]),
                        occurred_at=datetime.fromisoformat(
                            _fix_tz_offset(record["created"])
                        ),
                        event_type=record.get("summary", "unknown"),
                        payload=record,
                    )
                )

            total = data.get("total", 0)
            offset += len(records)
            if not records or offset >= total:
                break

        logger.info("jira cloud audit: fetched %d records", len(events))
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
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self._client.request(
                    method,
                    url,
                    auth=self._auth,
                    timeout=30.0,
                    **kwargs,  # type: ignore[arg-type]
                )
                if resp.status_code == 429:
                    wait = float(
                        resp.headers.get(
                            "Retry-After", _BACKOFF_BASE ** (attempt + 1)
                        )
                    )
                    logger.warning("jira: rate-limited, retrying in %.1fs", wait)
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp
            except httpx.TimeoutException:
                if attempt == _MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(_BACKOFF_BASE ** (attempt + 1))
        raise RuntimeError("max retries exceeded")


def _fix_tz_offset(s: str) -> str:
    if len(s) >= 5 and s[-5] in "+-" and s[-4:].isdigit():
        return s[:-5] + s[-5:-2] + ":" + s[-2:]
    return s
