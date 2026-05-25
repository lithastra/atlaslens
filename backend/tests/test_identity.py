import pytest

from atlaslens.normalize.identity import (
    backfill_actor_ids,
    resolve_identity,
)
from tests.mock_db import MockDB


class TestResolveIdentity:
    @pytest.mark.asyncio
    async def test_creates_new_identity(self) -> None:
        db = MockDB()
        result = await resolve_identity(
            db, "acct-1", "cloud", "jira", display_name="Alice"  # type: ignore[arg-type]
        )
        assert result is not None
        assert result.startswith("person:")
        doc = db["identities"].docs[result]
        assert doc["display_name"] == "Alice"
        assert len(doc["accounts"]) == 1
        assert doc["accounts"][0]["external_id"] == "acct-1"

    @pytest.mark.asyncio
    async def test_returns_none_for_empty_actor(self) -> None:
        db = MockDB()
        assert await resolve_identity(db, "", "cloud", "jira") is None  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_reuses_existing_identity(self) -> None:
        db = MockDB()
        id1 = await resolve_identity(
            db, "acct-1", "cloud", "jira"  # type: ignore[arg-type]
        )
        id2 = await resolve_identity(
            db, "acct-1", "cloud", "jira"  # type: ignore[arg-type]
        )
        assert id1 == id2
        assert len(db["identities"].docs) == 1

    @pytest.mark.asyncio
    async def test_adds_cross_product_link(self) -> None:
        db = MockDB()
        id1 = await resolve_identity(
            db, "acct-1", "cloud", "jira"  # type: ignore[arg-type]
        )
        id2 = await resolve_identity(
            db, "acct-1", "cloud", "confluence"  # type: ignore[arg-type]
        )
        assert id1 == id2
        doc = db["identities"].docs[id1]  # type: ignore[index]
        assert len(doc["accounts"]) == 2
        products = {a["product"] for a in doc["accounts"]}
        assert products == {"jira", "confluence"}

    @pytest.mark.asyncio
    async def test_does_not_duplicate_same_link(self) -> None:
        db = MockDB()
        await resolve_identity(
            db, "acct-1", "cloud", "jira"  # type: ignore[arg-type]
        )
        await resolve_identity(
            db, "acct-1", "cloud", "jira"  # type: ignore[arg-type]
        )
        doc = list(db["identities"].docs.values())[0]
        assert len(doc["accounts"]) == 1

    @pytest.mark.asyncio
    async def test_sets_display_name_on_first_resolve(self) -> None:
        db = MockDB()
        id1 = await resolve_identity(
            db, "acct-1", "cloud", "jira"  # type: ignore[arg-type]
        )
        await resolve_identity(
            db,  # type: ignore[arg-type]
            "acct-1",
            "cloud",
            "confluence",
            display_name="Alice",
        )
        doc = db["identities"].docs[id1]  # type: ignore[index]
        assert doc["display_name"] == "Alice"

    @pytest.mark.asyncio
    async def test_different_accounts_get_different_ids(self) -> None:
        db = MockDB()
        id1 = await resolve_identity(
            db, "acct-1", "cloud", "jira"  # type: ignore[arg-type]
        )
        id2 = await resolve_identity(
            db, "acct-2", "cloud", "jira"  # type: ignore[arg-type]
        )
        assert id1 != id2
        assert len(db["identities"].docs) == 2


class TestBackfillActorIds:
    @pytest.mark.asyncio
    async def test_backfills_events(self) -> None:
        db = MockDB()
        db["events"].docs["evt-1"] = {
            "_id": "evt-1",
            "actor_raw": "acct-1",
            "actor_id": None,
            "deployment": "cloud",
            "product": "jira",
        }
        db["events"].docs["evt-2"] = {
            "_id": "evt-2",
            "actor_raw": "acct-1",
            "actor_id": None,
            "deployment": "cloud",
            "product": "confluence",
        }

        updated = await backfill_actor_ids(db)  # type: ignore[arg-type]
        assert updated == 2

        evt1 = db["events"].docs["evt-1"]
        evt2 = db["events"].docs["evt-2"]
        assert evt1["actor_id"] is not None
        assert evt1["actor_id"] == evt2["actor_id"]

    @pytest.mark.asyncio
    async def test_skips_events_with_actor_id(self) -> None:
        db = MockDB()
        db["events"].docs["evt-1"] = {
            "_id": "evt-1",
            "actor_raw": "acct-1",
            "actor_id": "person:existing",
            "deployment": "cloud",
            "product": "jira",
        }

        updated = await backfill_actor_ids(db)  # type: ignore[arg-type]
        assert updated == 0

    @pytest.mark.asyncio
    async def test_skips_empty_actor_raw(self) -> None:
        db = MockDB()
        db["events"].docs["evt-1"] = {
            "_id": "evt-1",
            "actor_raw": "",
            "actor_id": None,
            "deployment": "cloud",
            "product": "jira",
        }

        updated = await backfill_actor_ids(db)  # type: ignore[arg-type]
        assert updated == 0
