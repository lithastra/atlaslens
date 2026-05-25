import httpx
import pytest

from atlaslens.connectors.cloud.confluence import (
    ConfluenceCloudConnector,
)


def _audit_response(
    results: list[dict],  # type: ignore[type-arg]
    total: int | None = None,
) -> dict:  # type: ignore[type-arg]
    if total is None:
        total = len(results)
    return {"results": results, "totalCount": total, "size": total}


def _record(
    record_id: int = 1,
    summary: str = "Space permission changed",
    created: str = "2026-04-10T08:00:00.000+0000",
) -> dict:  # type: ignore[type-arg]
    return {
        "id": record_id,
        "summary": summary,
        "creationDate": created,
        "remoteAddress": "10.0.0.1",
        "author": {"accountId": "conf-user-1", "username": "alice"},
        "category": "permissions",
        "objectItem": {
            "id": "sp-1",
            "name": "Engineering",
            "typeName": "SPACE",
        },
        "changedValues": [],
    }


class TestConfluenceCloudConnector:
    @pytest.mark.asyncio
    async def test_fetch_audit_basic(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200, json=_audit_response([_record(1), _record(2)])
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            conn = ConfluenceCloudConnector(
                "https://test.atlassian.net",
                ("e@x.com", "tok"),
                client,
            )
            events = await conn.fetch_audit(None)

        assert len(events) == 2

    @pytest.mark.asyncio
    async def test_fetch_audit_with_cursor(self) -> None:
        captured: list[dict] = []  # type: ignore[type-arg]

        def handler(req: httpx.Request) -> httpx.Response:
            captured.append(dict(req.url.params))
            return httpx.Response(
                200, json=_audit_response([_record()])
            )

        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            conn = ConfluenceCloudConnector(
                "https://test.atlassian.net",
                ("e@x.com", "tok"),
                client,
            )
            await conn.fetch_audit("2026-04-01T00:00:00+00:00")

        assert captured[0]["startDate"] == "2026-04-01T00:00:00+00:00"

    @pytest.mark.asyncio
    async def test_fetch_audit_empty(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(
                200, json=_audit_response([])
            )
        )
        async with httpx.AsyncClient(transport=transport) as client:
            conn = ConfluenceCloudConnector(
                "https://test.atlassian.net",
                ("e@x.com", "tok"),
                client,
            )
            events = await conn.fetch_audit(None)

        assert events == []

    @pytest.mark.asyncio
    async def test_fetch_activity_returns_empty(self) -> None:
        transport = httpx.MockTransport(
            lambda req: httpx.Response(200, json={})
        )
        async with httpx.AsyncClient(transport=transport) as client:
            conn = ConfluenceCloudConnector(
                "https://test.atlassian.net",
                ("e@x.com", "tok"),
                client,
            )
            events = await conn.fetch_activity(None)

        assert events == []
