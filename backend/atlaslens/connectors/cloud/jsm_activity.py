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


class JsmActivityConnector:
    """JSM Cloud activity via Jira search (JSM issues are Jira issues)."""

    product: Product = "jsm"
    deployment: Deployment = "cloud"

    def __init__(
        self,
        base_url: str,
        auth: tuple[str, str],
        client: httpx.AsyncClient,
        service_desk_projects: list[str] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._auth = auth
        self._client = client
        self._projects = service_desk_projects or []

    async def fetch_audit(self, cursor: Cursor) -> list[RawEvent]:
        return []

    async def fetch_activity(self, cursor: Cursor) -> list[RawEvent]:
        events: list[RawEvent] = []

        project_clause = ""
        if self._projects:
            keys = ", ".join(self._projects)
            project_clause = f"project in ({keys}) AND "

        jql = f"{project_clause}ORDER BY updated DESC"
        if cursor:
            jql = (
                f'{project_clause}updated >= "{cursor}" '
                f"ORDER BY updated ASC"
            )

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
                    "status",
                    "issuetype",
                    "project",
                    "reporter",
                ],
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

                event_type = (
                    "request_created"
                    if updated == created
                    else "request_updated"
                )
                events.append(
                    RawEvent(
                        source_id=f"jsm-{issue['key']}",
                        occurred_at=_parse_date(updated or created),
                        event_type=event_type,
                        payload=issue,
                    )
                )

            next_token = data.get("nextPageToken")
            if not issues or not next_token:
                break
            if next_token in seen_tokens:
                break
            seen_tokens.add(next_token)

        logger.info(
            "jsm cloud activity: fetched %d events", len(events)
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


def _parse_date(s: str) -> datetime:
    if not s:
        return datetime.now()
    if len(s) >= 5 and s[-5] in "+-" and s[-4:].isdigit():
        s = s[:-5] + s[-5:-2] + ":" + s[-2:]
    return datetime.fromisoformat(s)
