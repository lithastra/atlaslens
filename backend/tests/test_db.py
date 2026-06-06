from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from atlaslens import db as db_mod


@pytest.mark.asyncio
async def test_connect_db_is_timezone_aware() -> None:
    """Datetimes must come back from Mongo tz-aware (UTC); otherwise they
    serialize without an offset and the frontend renders them in the wrong
    timezone (e.g. "last sync" appearing hours stale).
    """
    fake_db = MagicMock()
    fake_client = MagicMock()
    fake_client.__getitem__.return_value = fake_db

    with (
        patch.object(
            db_mod, "AsyncIOMotorClient", return_value=fake_client
        ) as mock_client,
        patch.object(db_mod, "_create_indexes", new=AsyncMock()),
    ):
        await db_mod.connect_db()

    assert mock_client.call_args.kwargs.get("tz_aware") is True

    await db_mod.close_db()
