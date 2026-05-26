import logging
import re
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


async def upsert_canonical_group(
    db: AsyncIOMotorDatabase,
    group_id: str,
    name: str,
    description: str = "",
    source: str = "atlassian-org",
) -> None:
    await db["canonical_groups"].replace_one(
        {"_id": group_id},
        {
            "_id": group_id,
            "name": name,
            "description": description,
            "source": source,
            "active": True,
        },
        upsert=True,
    )


async def upsert_source_group(
    db: AsyncIOMotorDatabase,
    namespace: str,
    native_id: str,
    native_name: str,
    scope: str = "",
) -> str:
    doc_id = f"{namespace}:{native_id}"
    await db["source_groups"].replace_one(
        {"_id": doc_id},
        {
            "_id": doc_id,
            "namespace": namespace,
            "native_id": native_id,
            "native_name": native_name,
            "scope": scope,
            "last_seen": datetime.now(UTC),
        },
        upsert=True,
    )
    return doc_id


async def auto_map_groups(
    db: AsyncIOMotorDatabase,
) -> int:
    """Match unmapped source groups to canonical groups by name."""
    mapped = 0
    sg: dict[str, Any]
    async for sg in db["source_groups"].find():
        sg_id: str = sg["_id"]
        existing: dict[str, Any] | None = await db[  # type: ignore[func-returns-value]
            "group_map"
        ].find_one({"source_group_id": sg_id})
        if existing:
            continue

        native: str = sg["native_name"]
        cg: dict[str, Any] | None = await db[  # type: ignore[func-returns-value]
            "canonical_groups"
        ].find_one({"name": native})
        method = "auto_name"
        confidence = 1.0

        if not cg:
            pattern = f"^{re.escape(native)}$"
            cg = await db["canonical_groups"].find_one(  # type: ignore[func-returns-value]
                {"name": {"$regex": pattern, "$options": "i"}}
            )
            method = "auto_name_icase"
            confidence = 0.9

        if cg:
            await db["group_map"].replace_one(
                {"_id": f"map:{sg_id}"},
                {
                    "_id": f"map:{sg_id}",
                    "source_group_id": sg_id,
                    "canonical_group_id": cg["_id"],
                    "match_method": method,
                    "confidence": confidence,
                    "mapped_by": "system",
                    "mapped_at": datetime.now(UTC),
                },
                upsert=True,
            )
            mapped += 1

    logger.info("auto_map_groups: mapped %d source groups", mapped)
    return mapped


async def set_membership(
    db: AsyncIOMotorDatabase,
    canonical_group_id: str,
    identity_id: str,
) -> None:
    doc_id = f"{canonical_group_id}:{identity_id}"
    await db["group_membership"].replace_one(
        {"_id": doc_id},
        {
            "_id": doc_id,
            "canonical_group_id": canonical_group_id,
            "identity_id": identity_id,
            "added_at": datetime.now(UTC),
        },
        upsert=True,
    )


async def remove_membership(
    db: AsyncIOMotorDatabase,
    canonical_group_id: str,
    identity_id: str,
) -> None:
    doc_id = f"{canonical_group_id}:{identity_id}"
    await db["group_membership"].delete_one({"_id": doc_id})


async def get_members(
    db: AsyncIOMotorDatabase,
    canonical_group_id: str,
) -> list[str]:
    docs = db["group_membership"].find(
        {"canonical_group_id": canonical_group_id},
        {"identity_id": 1},
    )
    result: list[str] = []
    d: dict[str, Any]
    async for d in docs:
        result.append(d["identity_id"])
    return result


async def get_groups_for_identity(
    db: AsyncIOMotorDatabase,
    identity_id: str,
) -> list[str]:
    docs = db["group_membership"].find(
        {"identity_id": identity_id},
        {"canonical_group_id": 1},
    )
    result: list[str] = []
    d: dict[str, Any]
    async for d in docs:
        result.append(d["canonical_group_id"])
    return result


async def get_unmapped_source_groups(
    db: AsyncIOMotorDatabase,
) -> list[dict[str, Any]]:
    mapped_ids: set[str] = set()
    m: dict[str, Any]
    async for m in db["group_map"].find({}, {"source_group_id": 1}):
        mapped_ids.add(m["source_group_id"])

    unmapped: list[dict[str, Any]] = []
    sg: dict[str, Any]
    async for sg in db["source_groups"].find():
        if sg["_id"] not in mapped_ids:
            unmapped.append(sg)
    return unmapped
