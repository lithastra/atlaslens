from typing import Annotated, Any

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from atlaslens.api.deps import get_database

router = APIRouter(tags=["sync"])

DB = Annotated[
    AsyncIOMotorDatabase, Depends(get_database)
]

_CONNECTORS = [
    {"id": "cloud:jira:audit", "product": "jira", "deployment": "cloud"},
    {
        "id": "cloud:confluence:audit",
        "product": "confluence",
        "deployment": "cloud",
    },
    {"id": "cloud:jsm:audit", "product": "jsm", "deployment": "cloud"},
    {
        "id": "cloud:org:audit",
        "product": "jira",
        "deployment": "cloud",
        "note": "org events-stream",
    },
    {
        "id": "cloud:bitbucket:audit",
        "product": "bitbucket",
        "deployment": "cloud",
        "note": "UNAVAILABLE — requires Atlassian Guard",
    },
]


@router.get("/sync-status")
async def sync_status(db: DB) -> list[dict[str, Any]]:
    statuses: list[dict[str, Any]] = []
    for conn in _CONNECTORS:
        state: dict[str, Any] | None = await db["sync_state"].find_one(  # type: ignore[func-returns-value]
            {"_id": conn["id"]}
        )
        statuses.append({
            "connector": conn["id"],
            "product": conn["product"],
            "deployment": conn["deployment"],
            "cursor": state["cursor"] if state else None,
            "last_success_at": (
                state["last_success_at"] if state else None
            ),
            "last_error": state.get("last_error") if state else None,
            "note": conn.get("note"),
        })
    return statuses
