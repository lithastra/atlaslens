import asyncio
import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from atlaslens.api.deps import get_current_user, get_database
from atlaslens.db import get_db
from atlaslens.ingest.scheduler import run_all

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sync"])

DB = Annotated[
    AsyncIOMotorDatabase, Depends(get_database)
]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]

# Guards against overlapping manual syncs (and overlap with the scheduler).
# Single-process asyncio: the check-and-set in trigger_sync has no await
# between read and write, so it is effectively atomic.
_sync_running = False


async def _run_sync() -> None:
    global _sync_running
    try:
        results = await run_all(get_db())
        logger.info("Manual sync complete: %s", results)
    except Exception:
        logger.exception("Manual sync failed")
    finally:
        _sync_running = False

_CONNECTORS = [
    {"id": "cloud:jira:audit", "product": "jira", "deployment": "cloud"},
    {"id": "cloud:jsm:audit", "product": "jsm", "deployment": "cloud"},
    {
        "id": "cloud:confluence:audit",
        "product": "confluence",
        "deployment": "cloud",
    },
    {
        "id": "cloud:bitbucket:audit",
        "product": "bitbucket",
        "deployment": "cloud",
        "note": "UNAVAILABLE — requires Atlassian Guard",
    },
    {"id": "cloud:jira:activity", "product": "jira", "deployment": "cloud"},
    {
        "id": "cloud:confluence:activity",
        "product": "confluence",
        "deployment": "cloud",
    },
    {"id": "cloud:jsm:activity", "product": "jsm", "deployment": "cloud"},
    {
        "id": "cloud:bitbucket:activity",
        "product": "bitbucket",
        "deployment": "cloud",
    },
]


@router.post("/sync")
async def trigger_sync(_user: CurrentUser) -> dict[str, str]:
    """Kick off a full ingest (audit + activity + group sync) in the
    background and return immediately, so the request never blocks on the
    rate-limited pull. Re-entrant calls while a sync is in flight are no-ops.
    """
    global _sync_running
    if _sync_running:
        return {"status": "already_running"}
    _sync_running = True
    asyncio.create_task(_run_sync())
    return {"status": "started"}


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
            "cursor": state.get("cursor") if state else None,
            "last_success_at": (
                state.get("last_success_at") if state else None
            ),
            "last_error": state.get("last_error") if state else None,
            "note": conn.get("note"),
        })
    return statuses
