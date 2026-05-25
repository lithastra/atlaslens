import asyncio
import logging
from datetime import datetime

import httpx

from atlaslens.connectors.base import Cursor, RawEvent
from atlaslens.models.event import Deployment, Product

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0
_PAGE_LEN = 50


class BitbucketActivityConnector:
    """Bitbucket Cloud commits and PRs (no Guard needed)."""

    product: Product = "bitbucket"
    deployment: Deployment = "cloud"

    def __init__(
        self,
        workspace: str,
        auth: tuple[str, str],
        client: httpx.AsyncClient,
        repositories: list[str] | None = None,
    ) -> None:
        self._workspace = workspace
        self._auth = auth
        self._client = client
        self._repos = repositories or []

    async def fetch_audit(self, cursor: Cursor) -> list[RawEvent]:
        return []

    async def fetch_activity(self, cursor: Cursor) -> list[RawEvent]:
        events: list[RawEvent] = []
        repos = self._repos or await self._list_repos()

        for repo in repos:
            events.extend(await self._fetch_commits(repo, cursor))
            events.extend(await self._fetch_pull_requests(repo, cursor))

        logger.info(
            "bitbucket cloud activity: fetched %d events",
            len(events),
        )
        return events

    async def _list_repos(self) -> list[str]:
        resp = await self._request(
            "GET",
            f"https://api.bitbucket.org/2.0/repositories/"
            f"{self._workspace}?pagelen=100",
        )
        data = resp.json()
        repos: list[str] = []
        for repo in data.get("values", []):
            slug = repo.get("slug", "")
            if slug:
                repos.append(slug)
        return repos

    async def _fetch_commits(
        self, repo: str, cursor: Cursor
    ) -> list[RawEvent]:
        events: list[RawEvent] = []
        next_url: str | None = (
            f"https://api.bitbucket.org/2.0/repositories/"
            f"{self._workspace}/{repo}/commits?pagelen={_PAGE_LEN}"
        )

        while next_url:
            resp = await self._request("GET", next_url)
            data = resp.json()
            values: list[dict] = data.get("values", [])  # type: ignore[type-arg]

            for commit in values:
                date_str = commit.get("date", "")
                if cursor and date_str and date_str < cursor:
                    return events

                author = commit.get("author", {})
                user = author.get("user", {})
                events.append(
                    RawEvent(
                        source_id=commit.get("hash", "")[:12],
                        occurred_at=_parse_date(date_str),
                        event_type="commit_pushed",
                        payload={
                            "hash": commit.get("hash", ""),
                            "message": commit.get("message", ""),
                            "repo": repo,
                            "author": {
                                "raw": author.get("raw", ""),
                                "account_id": user.get(
                                    "account_id", ""
                                ),
                            },
                        },
                    )
                )

            next_url = data.get("next")

        return events

    async def _fetch_pull_requests(
        self, repo: str, cursor: Cursor
    ) -> list[RawEvent]:
        events: list[RawEvent] = []
        next_url: str | None = (
            f"https://api.bitbucket.org/2.0/repositories/"
            f"{self._workspace}/{repo}/pullrequests"
            f"?pagelen={_PAGE_LEN}&state=MERGED&state=OPEN"
            f"&sort=-updated_on"
        )

        while next_url:
            resp = await self._request("GET", next_url)
            data = resp.json()
            values: list[dict] = data.get("values", [])  # type: ignore[type-arg]

            for pr in values:
                updated = pr.get("updated_on", "")
                if cursor and updated and updated < cursor:
                    return events

                author = pr.get("author", {})
                state = pr.get("state", "OPEN")
                event_type = (
                    "pull_request_merged"
                    if state == "MERGED"
                    else "pull_request_opened"
                )
                events.append(
                    RawEvent(
                        source_id=f"pr-{repo}-{pr.get('id', '')}",
                        occurred_at=_parse_date(updated),
                        event_type=event_type,
                        payload={
                            "id": pr.get("id"),
                            "title": pr.get("title", ""),
                            "repo": repo,
                            "state": state,
                            "author": {
                                "account_id": author.get(
                                    "account_id", ""
                                ),
                                "display_name": author.get(
                                    "display_name", ""
                                ),
                            },
                            "source_branch": (
                                pr.get("source", {})
                                .get("branch", {})
                                .get("name", "")
                            ),
                            "destination_branch": (
                                pr.get("destination", {})
                                .get("branch", {})
                                .get("name", "")
                            ),
                        },
                    )
                )

            next_url = data.get("next")

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
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    if len(s) >= 5 and s[-5] in "+-" and s[-4:].isdigit():
        s = s[:-5] + s[-5:-2] + ":" + s[-2:]
    return datetime.fromisoformat(s)
