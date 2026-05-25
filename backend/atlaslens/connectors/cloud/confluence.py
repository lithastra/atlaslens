import asyncio
import logging
from datetime import datetime

import httpx

from atlaslens.connectors.base import Cursor, RawEvent
from atlaslens.models.event import Deployment, Product

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0
_PAGE_LIMIT = 1000


class ConfluenceCloudConnector:
    product: Product = "confluence"
    deployment: Deployment = "cloud"

    def __init__(
        self,
        base_url: str,
        auth: tuple[str, str],
        client: httpx.AsyncClient,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = auth
        self._client = client

    async def fetch_audit(self, cursor: Cursor) -> list[RawEvent]:
        events: list[RawEvent] = []
        start = 0

        while True:
            params: dict[str, str | int] = {
                "limit": _PAGE_LIMIT,
                "start": start,
            }
            if cursor:
                params["startDate"] = cursor

            resp = await self._request(
                "GET",
                f"{self._base_url}/wiki/rest/api/audit",
                params=params,
            )
            data = resp.json()
            results: list[dict] = data.get("results", [])  # type: ignore[type-arg]

            for record in results:
                created = record.get("creationDate", "")
                events.append(
                    RawEvent(
                        source_id=str(record.get("id", start + len(events))),
                        occurred_at=_parse_confluence_date(created),
                        event_type=record.get("summary", "unknown"),
                        payload=record,
                    )
                )

            total = data.get("totalCount", data.get("size", 0))
            start += len(results)
            if not results or start >= total:
                break

        logger.info(
            "confluence cloud audit: fetched %d records", len(events)
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
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await self._client.request(
                    method,
                    url,
                    auth=self._auth,  # type: ignore[arg-type]
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
                        "confluence: rate-limited, retrying in %.1fs", wait
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


def _parse_confluence_date(s: str) -> datetime:
    if not s:
        return datetime.now()
    if len(s) >= 5 and s[-5] in "+-" and s[-4:].isdigit():
        s = s[:-5] + s[-5:-2] + ":" + s[-2:]
    return datetime.fromisoformat(s)
