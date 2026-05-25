from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, TEXT

from atlaslens.config import settings

_client: AsyncIOMotorClient | None = None  # type: ignore[type-arg]
_db: AsyncIOMotorDatabase | None = None  # type: ignore[type-arg]


async def connect_db() -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    global _client, _db
    _client = AsyncIOMotorClient(settings.mongo_uri)
    _db = _client[settings.mongo_db]
    await _create_indexes(_db)
    return _db


async def close_db() -> None:
    global _client, _db
    if _client:
        _client.close()
    _client = None
    _db = None


def get_db() -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    if _db is None:
        raise RuntimeError("Database not connected — call connect_db() first")
    return _db


async def _create_indexes(db: AsyncIOMotorDatabase) -> None:  # type: ignore[type-arg]
    events = db["events"]
    await events.create_index([("occurred_at", DESCENDING)])
    await events.create_index([("product", ASCENDING), ("occurred_at", DESCENDING)])
    await events.create_index([("actor_id", ASCENDING), ("occurred_at", DESCENDING)])
    await events.create_index(
        [
            ("category", ASCENDING),
            ("severity", ASCENDING),
            ("occurred_at", DESCENDING),
        ]
    )
    await events.create_index([("operation", ASCENDING), ("occurred_at", DESCENDING)])
    await events.create_index(
        [("occurred_at", ASCENDING)],
        expireAfterSeconds=31_536_000,
    )
    await events.create_index(
        [("object_ref.name", TEXT), ("actor_raw", TEXT), ("operation", TEXT)]
    )

    users = db["users"]
    await users.create_index("username", unique=True)

    identities = db["identities"]
    await identities.create_index("accounts.external_id")

    source_groups = db["source_groups"]
    await source_groups.create_index(
        [("namespace", ASCENDING), ("native_id", ASCENDING)], unique=True
    )

    group_map = db["group_map"]
    await group_map.create_index("source_group_id")
    await group_map.create_index("canonical_group_id")
