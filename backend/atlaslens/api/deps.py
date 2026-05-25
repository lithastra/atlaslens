from motor.motor_asyncio import AsyncIOMotorDatabase

from atlaslens.db import get_db


async def get_database() -> AsyncIOMotorDatabase:  # type: ignore[type-arg]
    return get_db()
