import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_returns_ok(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "collections" in data


@pytest.mark.asyncio
async def test_health_lists_collections(client: AsyncClient) -> None:
    resp = await client.get("/health")
    data = resp.json()
    assert "events" in data["collections"]
    assert "users" in data["collections"]
