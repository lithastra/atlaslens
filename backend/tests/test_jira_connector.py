import httpx
import pytest

from atlaslens.connectors.cloud.jira import JiraCloudConnector, _fix_tz_offset


def _audit_response(records: list[dict], total: int | None = None) -> dict:  # type: ignore[type-arg]
    if total is None:
        total = len(records)
    return {"offset": 0, "limit": 1000, "total": total, "records": records}


def _record(
    record_id: int = 1,
    summary: str = "User added to group",
    created: str = "2026-03-15T10:30:00.000+0000",
) -> dict:  # type: ignore[type-arg]
    return {
        "id": record_id,
        "summary": summary,
        "remoteAddress": "192.168.1.1",
        "authorAccountId": "5f8abc",
        "created": created,
        "category": "group management",
        "eventSource": "Jira",
        "objectItem": {
            "id": "123",
            "name": "jira-administrators",
            "typeName": "GROUP",
        },
        "changedValues": [],
        "associatedItems": [],
    }


class TestJiraCloudConnector:
    @pytest.mark.asyncio
    async def test_fetch_audit_single_page(self) -> None:
        records = [
            _record(i, created=f"2026-03-{10+i:02d}T00:00:00.000+0000")
            for i in range(3)
        ]

        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=_audit_response(records))
        )
        async with httpx.AsyncClient(transport=transport) as client:
            connector = JiraCloudConnector(
                base_url="https://test.atlassian.net",
                auth=("e@x.com", "tok"),
                client=client,
            )
            events = await connector.fetch_audit(None)

        assert len(events) == 3
        assert events[0].source_id == "0"
        assert events[1].source_id == "1"
        assert events[2].source_id == "2"

    @pytest.mark.asyncio
    async def test_fetch_audit_with_cursor(self) -> None:
        captured_params: list[dict] = []  # type: ignore[type-arg]

        def handler(request: httpx.Request) -> httpx.Response:
            captured_params.append(dict(request.url.params))
            return httpx.Response(200, json=_audit_response([_record()]))

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            connector = JiraCloudConnector(
                base_url="https://test.atlassian.net",
                auth=("e@x.com", "tok"),
                client=client,
            )
            await connector.fetch_audit("2026-03-01T00:00:00+00:00")

        assert captured_params[0]["from"] == "2026-03-01T00:00:00+00:00"

    @pytest.mark.asyncio
    async def test_fetch_audit_pagination(self) -> None:
        call_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal call_count
            offset = int(request.url.params.get("offset", "0"))
            call_count += 1
            if offset == 0:
                return httpx.Response(
                    200,
                    json={
                        "offset": 0,
                        "limit": 2,
                        "total": 4,
                        "records": [_record(1), _record(2)],
                    },
                )
            return httpx.Response(
                200,
                json={
                    "offset": 2,
                    "limit": 2,
                    "total": 4,
                    "records": [_record(3), _record(4)],
                },
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            connector = JiraCloudConnector(
                base_url="https://test.atlassian.net",
                auth=("e@x.com", "tok"),
                client=client,
            )
            events = await connector.fetch_audit(None)

        assert len(events) == 4
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_audit_empty(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json=_audit_response([]))
        )
        async with httpx.AsyncClient(transport=transport) as client:
            connector = JiraCloudConnector(
                base_url="https://test.atlassian.net",
                auth=("e@x.com", "tok"),
                client=client,
            )
            events = await connector.fetch_audit(None)

        assert events == []

    @pytest.mark.asyncio
    async def test_fetch_activity_returns_empty(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json={})
        )
        async with httpx.AsyncClient(transport=transport) as client:
            connector = JiraCloudConnector(
                base_url="https://test.atlassian.net",
                auth=("e@x.com", "tok"),
                client=client,
            )
            events = await connector.fetch_activity(None)

        assert events == []


class TestFixTzOffset:
    def test_plus_without_colon(self) -> None:
        result = _fix_tz_offset("2026-03-15T10:30:00.000+0000")
        assert result == "2026-03-15T10:30:00.000+00:00"

    def test_minus_without_colon(self) -> None:
        result = _fix_tz_offset("2026-03-15T10:30:00.000-0500")
        assert result == "2026-03-15T10:30:00.000-05:00"

    def test_already_has_colon(self) -> None:
        s = "2026-03-15T10:30:00.000+00:00"
        assert _fix_tz_offset(s) == s

    def test_no_offset(self) -> None:
        s = "2026-03-15T10:30:00Z"
        assert _fix_tz_offset(s) == s
