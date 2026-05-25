import httpx
import pytest

from atlaslens.connectors.cloud.bitbucket_activity import (
    BitbucketActivityConnector,
)
from atlaslens.connectors.cloud.confluence_activity import (
    ConfluenceActivityConnector,
)
from atlaslens.connectors.cloud.jira_activity import (
    JiraActivityConnector,
)
from atlaslens.connectors.cloud.jsm_activity import (
    JsmActivityConnector,
)


def _jira_search_response(
    issues: list[dict],  # type: ignore[type-arg]
    next_token: str | None = None,
) -> dict:  # type: ignore[type-arg]
    r: dict = {"issues": issues}  # type: ignore[type-arg]
    if next_token:
        r["nextPageToken"] = next_token
    return r


def _jira_issue(
    key: str = "PROJ-1",
    updated: str = "2026-04-20T10:00:00.000+0000",
    created: str = "2026-04-18T08:00:00.000+0000",
) -> dict:  # type: ignore[type-arg]
    return {
        "key": key,
        "fields": {
            "key": key,
            "summary": "Test issue",
            "updated": updated,
            "created": created,
            "creator": {"accountId": "user-1"},
            "status": {"name": "Open"},
            "issuetype": {"name": "Task"},
            "project": {"key": "PROJ"},
        },
        "changelog": {"histories": []},
    }


class TestJiraActivityConnector:
    @pytest.mark.asyncio
    async def test_fetch_activity_basic(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json=_jira_search_response([_jira_issue()]),
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            conn = JiraActivityConnector(
                "https://test.atlassian.net",
                ("e@x.com", "tok"),
                client,
            )
            events = await conn.fetch_activity(None)

        assert len(events) >= 1
        assert events[0].source_id == "PROJ-1"

    @pytest.mark.asyncio
    async def test_changelog_produces_events(self) -> None:
        issue = _jira_issue()
        issue["changelog"] = {
            "histories": [
                {
                    "id": "cl-1",
                    "created": "2026-04-20T10:00:00.000+0000",
                    "author": {"accountId": "user-1"},
                    "items": [
                        {
                            "field": "status",
                            "fromString": "Open",
                            "toString": "Done",
                        }
                    ],
                }
            ]
        }
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json=_jira_search_response([issue]),
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            conn = JiraActivityConnector(
                "https://test.atlassian.net",
                ("e@x.com", "tok"),
                client,
            )
            events = await conn.fetch_activity(None)

        assert len(events) == 2
        assert events[1].event_type == "issue_transitioned"

    @pytest.mark.asyncio
    async def test_stops_on_repeating_token(self) -> None:
        call_count = 0

        def handler(req: httpx.Request) -> httpx.Response:
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                200,
                json=_jira_search_response(
                    [_jira_issue()], next_token="same"
                ),
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            conn = JiraActivityConnector(
                "https://test.atlassian.net",
                ("e@x.com", "tok"),
                client,
            )
            events = await conn.fetch_activity(None)

        assert call_count == 2
        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_fetch_audit_returns_empty(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json={})
        )
        async with httpx.AsyncClient(transport=transport) as client:
            conn = JiraActivityConnector(
                "https://test.atlassian.net",
                ("e@x.com", "tok"),
                client,
            )
            assert await conn.fetch_audit(None) == []


class TestConfluenceActivityConnector:
    @pytest.mark.asyncio
    async def test_fetch_activity_basic(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "pg-1",
                            "title": "Roadmap",
                            "createdAt": "2026-04-01T00:00:00Z",
                            "spaceId": "ENG",
                            "status": "current",
                            "version": {
                                "number": 3,
                                "createdAt": "2026-04-20T10:00:00Z",
                                "authorId": "u1",
                            },
                        }
                    ],
                    "_links": {},
                },
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            conn = ConfluenceActivityConnector(
                "https://test.atlassian.net",
                ("e@x.com", "tok"),
                client,
            )
            events = await conn.fetch_activity(None)

        assert len(events) == 1
        assert events[0].event_type == "page_edited"

    @pytest.mark.asyncio
    async def test_page_created_on_v1(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json={
                    "results": [
                        {
                            "id": "pg-2",
                            "title": "New page",
                            "createdAt": "2026-04-20T10:00:00Z",
                            "spaceId": "ENG",
                            "status": "current",
                            "version": {
                                "number": 1,
                                "createdAt": "2026-04-20T10:00:00Z",
                                "authorId": "u1",
                            },
                        }
                    ],
                    "_links": {},
                },
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            conn = ConfluenceActivityConnector(
                "https://test.atlassian.net",
                ("e@x.com", "tok"),
                client,
            )
            events = await conn.fetch_activity(None)

        assert events[0].event_type == "page_created"


class TestBitbucketActivityConnector:
    @pytest.mark.asyncio
    async def test_fetch_commits(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            if "/commits" in str(req.url):
                return httpx.Response(
                    200,
                    json={
                        "values": [
                            {
                                "hash": "abc123def456",
                                "date": "2026-04-20T10:00:00+00:00",
                                "message": "Fix bug",
                                "author": {
                                    "raw": "Alice <a@x.com>",
                                    "user": {"account_id": "u1"},
                                },
                            }
                        ]
                    },
                )
            if "/pullrequests" in str(req.url):
                return httpx.Response(
                    200, json={"values": []}
                )
            return httpx.Response(200, json={"values": []})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            conn = BitbucketActivityConnector(
                "myws",
                ("user", "pass"),
                client,
                repositories=["my-repo"],
            )
            events = await conn.fetch_activity(None)

        assert len(events) == 1
        assert events[0].event_type == "commit_pushed"
        assert events[0].source_id == "abc123def456"

    @pytest.mark.asyncio
    async def test_fetch_prs(self) -> None:
        def handler(req: httpx.Request) -> httpx.Response:
            if "/commits" in str(req.url):
                return httpx.Response(
                    200, json={"values": []}
                )
            if "/pullrequests" in str(req.url):
                return httpx.Response(
                    200,
                    json={
                        "values": [
                            {
                                "id": 42,
                                "title": "Add feature",
                                "updated_on": "2026-04-20T10:00:00+00:00",
                                "state": "MERGED",
                                "author": {
                                    "account_id": "u1",
                                    "display_name": "Alice",
                                },
                                "source": {
                                    "branch": {"name": "feat"}
                                },
                                "destination": {
                                    "branch": {"name": "main"}
                                },
                            }
                        ]
                    },
                )
            return httpx.Response(200, json={"values": []})

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            conn = BitbucketActivityConnector(
                "myws",
                ("user", "pass"),
                client,
                repositories=["my-repo"],
            )
            events = await conn.fetch_activity(None)

        assert len(events) == 1
        assert events[0].event_type == "pull_request_merged"


class TestJsmActivityConnector:
    @pytest.mark.asyncio
    async def test_fetch_activity_basic(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json=_jira_search_response([
                    {
                        "key": "SD-100",
                        "fields": {
                            "summary": "VPN access",
                            "updated": "2026-04-20T10:00:00.000+0000",
                            "created": "2026-04-20T10:00:00.000+0000",
                            "creator": {"accountId": "u1"},
                            "status": {"name": "Open"},
                            "issuetype": {"name": "Service Request"},
                            "project": {"key": "SD"},
                        },
                    }
                ]),
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            conn = JsmActivityConnector(
                "https://test.atlassian.net",
                ("e@x.com", "tok"),
                client,
            )
            events = await conn.fetch_activity(None)

        assert len(events) == 1
        assert events[0].source_id == "jsm-SD-100"
        assert events[0].event_type == "request_created"
