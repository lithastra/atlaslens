from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from atlaslens.api.deps import get_database
from atlaslens.api.main import app


def _make_mock_db() -> MagicMock:
    db = MagicMock()
    db.command = AsyncMock(return_value={"ok": 1})
    db.list_collection_names = AsyncMock(
        return_value=["events", "users", "identities", "sync_state"]
    )
    return db


@pytest.fixture
def mock_db() -> MagicMock:
    return _make_mock_db()


@pytest.fixture
async def client(mock_db: MagicMock) -> AsyncIterator[AsyncClient]:
    app.dependency_overrides[get_database] = lambda: mock_db
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
