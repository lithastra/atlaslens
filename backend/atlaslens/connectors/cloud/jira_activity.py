import asyncio
import logging
from datetime import datetime

import httpx

from atlaslens.connectors.base import Cursor, RawEvent
from atlaslens.models.event import Deployment, Product

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0
_PAGE_SIZE = 100


class JiraActivityConnector:
    """Jira Cloud activity via POST /rest/api/3/search/jql.

    Uses nextPageToken pagination (old GET /search is removed).
    Fetches issues updated since the cursor with changelog expanded.
    """

    product: Product = "jira"
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
        return []

    async def fetch_activity(self, cursor: Cursor) -> list[RawEvent]:
        events: list[RawEvent] = []
        jql = "ORDER BY updated DESC"
        if cursor:
            jql = f'updated >= "{cursor}" ORDER BY updated ASC'

        next_token: str | None = None
        seen_tokens: set[str] = set()

        while True:
            body: dict[str, object] = {
                "jql": jql,
                "maxResults": _PAGE_SIZE,
                "fields": [
                    "key",
                    "summary",
                    "updated",
                    "created",
                    "creator",
                    "assignee",
                    "status",
                    "issuetype",
                    "project",
                ],
                "expand": "changelog",
            }
            if next_token:
                body["nextPageToken"] = next_token

            resp = await self._request(
                "POST",
                f"{self._base_url}/rest/api/3/search/jql",
                json=body,
            )
            data = resp.json()
            issues: list[dict] = data.get("issues", [])  # type: ignore[type-arg]

            for issue in issues:
                fields = issue.get("fields", {})
                updated = fields.get("updated", "")
                created = fields.get("created", "")

                events.append(
                    RawEvent(
                        source_id=issue["key"],
                        occurred_at=_parse_date(updated or created),
                        event_type=(
                            "issue_created"
                            if updated == created
                            else "issue_updated"
                        ),
                        payload=issue,
                    )
                )

                for item in _changelog_items(issue):
                    events.append(item)

            next_token = data.get("nextPageToken")
            if not issues or not next_token:
                break
            if next_token in seen_tokens:
                logger.warning("jira activity: repeating token, stopping")
                break
            seen_tokens.add(next_token)

        logger.info(
            "jira cloud activity: fetched %d events", len(events)
        )
        return events

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
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp
            except httpx.TimeoutException:
                if attempt == _MAX_RETRIES - 1:
                    raise
                await asyncio.sleep(_BACKOFF_BASE ** (attempt + 1))
        raise RuntimeError("max retries exceeded")


def _changelog_items(issue: dict) -> list[RawEvent]:  # type: ignore[type-arg]
    items: list[RawEvent] = []
    changelog = issue.get("changelog", {})
    histories: list[dict] = changelog.get("histories", [])  # type: ignore[type-arg]
    key = issue.get("key", "")
    for history in histories:
        author = history.get("author", {})
        items.append(
            RawEvent(
                source_id=f"{key}-cl-{history.get('id', '')}",
                occurred_at=_parse_date(history.get("created", "")),
                event_type="issue_transitioned",
                payload={
                    "issue_key": key,
                    "changelog_id": history.get("id"),
                    "author": author,
                    "items": history.get("items", []),
                },
            )
        )
    return items


def _parse_date(s: str) -> datetime:
    if not s:
        return datetime.now()
    if len(s) >= 5 and s[-5] in "+-" and s[-4:].isdigit():
        s = s[:-5] + s[-5:-2] + ":" + s[-2:]
    return datetime.fromisoformat(s)
