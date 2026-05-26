from typing import Annotated, Any

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from atlaslens.api.deps import get_database

router = APIRouter(tags=["health"])

DB = Annotated[AsyncIOMotorDatabase, Depends(get_database)]


@router.get("/health")
async def health(db: DB) -> dict[str, Any]:
    await db.command("ping")
    collections = await db.list_collection_names()
    return {
        "status": "ok",
        "database": "connected",
        "collections": collections,
    }
