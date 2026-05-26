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
_PAGE_LIMIT = 50


class ConfluenceActivityConnector:
    """Confluence Cloud activity via v2 pages API + version history."""

    product: Product = "confluence"
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
        return []

    async def fetch_activity(self, cursor: Cursor) -> list[RawEvent]:
        events: list[RawEvent] = []
        next_url: str | None = (
            f"{self._base_url}/wiki/api/v2/pages"
            f"?limit={_PAGE_LIMIT}&sort=-modified-date"
        )

        while next_url:
            resp = await self._request("GET", next_url)
            data = resp.json()
            pages: list[dict[str, Any]] = data.get("results", [])

            for page in pages:
                page_id = page.get("id", "")
                title = page.get("title", "")
                created = page.get("createdAt", "")
                version = page.get("version", {})
                updated = version.get("createdAt", created)
                author = version.get("authorId", "")

                if cursor and updated < cursor:
                    next_url = None
                    break

                event_type = (
                    "page_created"
                    if version.get("number", 1) == 1
                    else "page_edited"
                )
                events.append(
                    RawEvent(
                        source_id=f"page-{page_id}-v{version.get('number', 1)}",
                        occurred_at=_parse_date(updated),
                        event_type=event_type,
                        payload={
                            "page_id": page_id,
                            "title": title,
                            "space_id": page.get("spaceId", ""),
                            "version": version,
                            "author_id": author,
                            "status": page.get("status", ""),
                        },
                    )
                )
            else:
                links = data.get("_links", {})
                next_link = links.get("next")
                if next_link and next_link.startswith("/"):
                    next_url = f"{self._base_url}{next_link}"
                elif next_link:
                    next_url = next_link
                else:
                    next_url = None
                continue
            break

        logger.info(
            "confluence cloud activity: fetched %d events",
            len(events),
        )
        return events

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
                            "Retry-After",
                            _BACKOFF_BASE ** (attempt + 1),
                        )
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
