import pytest

from atlaslens.normalize.groups import (
    auto_map_groups,
    get_groups_for_identity,
    get_members,
    get_unmapped_source_groups,
    remove_membership,
    set_membership,
    upsert_canonical_group,
    upsert_source_group,
)
from tests.mock_db import MockDB


class TestCanonicalGroups:
    @pytest.mark.asyncio
    async def test_upsert_creates(self) -> None:
        db = MockDB()
        await upsert_canonical_group(
            db, "grp-eng", "Engineering"  # type: ignore[arg-type]
        )
        doc = db["canonical_groups"].docs["grp-eng"]
        assert doc["name"] == "Engineering"
        assert doc["active"] is True

    @pytest.mark.asyncio
    async def test_upsert_updates(self) -> None:
        db = MockDB()
        await upsert_canonical_group(
            db, "grp-eng", "Engineering"  # type: ignore[arg-type]
        )
        await upsert_canonical_group(
            db,  # type: ignore[arg-type]
            "grp-eng",
            "Engineering",
            description="The eng team",
        )
        doc = db["canonical_groups"].docs["grp-eng"]
        assert doc["description"] == "The eng team"


class TestSourceGroups:
    @pytest.mark.asyncio
    async def test_upsert_returns_id(self) -> None:
        db = MockDB()
        sg_id = await upsert_source_group(
            db,  # type: ignore[arg-type]
            "atlassian-org",
            "g-123",
            "Engineering",
        )
        assert sg_id == "atlassian-org:g-123"
        assert sg_id in db["source_groups"].docs


class TestAutoMapGroups:
    @pytest.mark.asyncio
    async def test_exact_name_match(self) -> None:
        db = MockDB()
        await upsert_canonical_group(
            db, "grp-eng", "Engineering"  # type: ignore[arg-type]
        )
        await upsert_source_group(
            db,  # type: ignore[arg-type]
            "atlassian-org",
            "g-123",
            "Engineering",
        )

        mapped = await auto_map_groups(db)  # type: ignore[arg-type]
        assert mapped == 1
        gm = db["group_map"].docs["map:atlassian-org:g-123"]
        assert gm["canonical_group_id"] == "grp-eng"
        assert gm["match_method"] == "auto_name"
        assert gm["confidence"] == 1.0

    @pytest.mark.asyncio
    async def test_case_insensitive_match(self) -> None:
        db = MockDB()
        await upsert_canonical_group(
            db, "grp-eng", "Engineering"  # type: ignore[arg-type]
        )
        await upsert_source_group(
            db,  # type: ignore[arg-type]
            "atlassian-org",
            "g-456",
            "engineering",
        )

        mapped = await auto_map_groups(db)  # type: ignore[arg-type]
        assert mapped == 1
        gm = db["group_map"].docs["map:atlassian-org:g-456"]
        assert gm["match_method"] == "auto_name_icase"
        assert gm["confidence"] == 0.9

    @pytest.mark.asyncio
    async def test_no_match_leaves_unmapped(self) -> None:
        db = MockDB()
        await upsert_source_group(
            db,  # type: ignore[arg-type]
            "bitbucket",
            "bb-team",
            "DevOps",
        )

        mapped = await auto_map_groups(db)  # type: ignore[arg-type]
        assert mapped == 0
        assert len(db["group_map"].docs) == 0

    @pytest.mark.asyncio
    async def test_already_mapped_skipped(self) -> None:
        db = MockDB()
        await upsert_canonical_group(
            db, "grp-eng", "Engineering"  # type: ignore[arg-type]
        )
        await upsert_source_group(
            db,  # type: ignore[arg-type]
            "atlassian-org",
            "g-123",
            "Engineering",
        )
        await auto_map_groups(db)  # type: ignore[arg-type]
        mapped = await auto_map_groups(db)  # type: ignore[arg-type]
        assert mapped == 0


class TestMembership:
    @pytest.mark.asyncio
    async def test_set_and_get_members(self) -> None:
        db = MockDB()
        await set_membership(
            db, "grp-eng", "person:001"  # type: ignore[arg-type]
        )
        await set_membership(
            db, "grp-eng", "person:002"  # type: ignore[arg-type]
        )

        members = await get_members(db, "grp-eng")  # type: ignore[arg-type]
        assert sorted(members) == ["person:001", "person:002"]

    @pytest.mark.asyncio
    async def test_remove_membership(self) -> None:
        db = MockDB()
        await set_membership(
            db, "grp-eng", "person:001"  # type: ignore[arg-type]
        )
        await remove_membership(
            db, "grp-eng", "person:001"  # type: ignore[arg-type]
        )

        members = await get_members(db, "grp-eng")  # type: ignore[arg-type]
        assert members == []

    @pytest.mark.asyncio
    async def test_get_groups_for_identity(self) -> None:
        db = MockDB()
        await set_membership(
            db, "grp-eng", "person:001"  # type: ignore[arg-type]
        )
        await set_membership(
            db, "grp-ops", "person:001"  # type: ignore[arg-type]
        )

        groups = await get_groups_for_identity(
            db, "person:001"  # type: ignore[arg-type]
        )
        assert sorted(groups) == ["grp-eng", "grp-ops"]

    @pytest.mark.asyncio
    async def test_idempotent_set(self) -> None:
        db = MockDB()
        await set_membership(
            db, "grp-eng", "person:001"  # type: ignore[arg-type]
        )
        await set_membership(
            db, "grp-eng", "person:001"  # type: ignore[arg-type]
        )

        members = await get_members(db, "grp-eng")  # type: ignore[arg-type]
        assert members == ["person:001"]


class TestUnmappedGroups:
    @pytest.mark.asyncio
    async def test_returns_unmapped(self) -> None:
        db = MockDB()
        await upsert_canonical_group(
            db, "grp-eng", "Engineering"  # type: ignore[arg-type]
        )
        await upsert_source_group(
            db,  # type: ignore[arg-type]
            "atlassian-org",
            "g-123",
            "Engineering",
        )
        await upsert_source_group(
            db,  # type: ignore[arg-type]
            "bitbucket",
            "bb-dev",
            "DevOps",
        )
        await auto_map_groups(db)  # type: ignore[arg-type]

        unmapped = await get_unmapped_source_groups(db)  # type: ignore[arg-type]
        assert len(unmapped) == 1
        assert unmapped[0]["native_name"] == "DevOps"
