from typing import Annotated, Any

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from atlaslens.api.deps import get_current_user, get_database
from atlaslens.db import get_db
from atlaslens.ingest.manager import manager
from atlaslens.ingest.scheduler import GROUPS_ID

router = APIRouter(tags=["sync"])

DB = Annotated[
    AsyncIOMotorDatabase, Depends(get_database)
]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]

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
    {
        "id": GROUPS_ID,
        "product": "groups",
        "deployment": "cloud",
        "note": "Org groups + memberships",
    },
]


@router.post("/sync")
async def trigger_sync(_user: CurrentUser) -> dict[str, str]:
    """Start a full ingest (audit + activity + group sync) in the background
    and return immediately. Only one sync runs at a time: if one is already
    in flight it is cancelled and replaced by this one.
    """
    status = await manager.start(get_db(), cancel_existing=True)
    return {"status": status}


def _derive_state(
    live: dict[str, Any] | None,
    state_doc: dict[str, Any] | None,
) -> tuple[str, int | None]:
    if live:
        return live.get("state", "idle"), live.get("count")
    if state_doc and state_doc.get("last_error"):
        return "error", None
    if state_doc and state_doc.get("last_success_at"):
        return "ok", None
    return "idle", None


@router.get("/sync-status")
async def sync_status(db: DB) -> dict[str, Any]:
    snap = manager.snapshot()
    live: dict[str, Any] = snap["connectors"]

    statuses: list[dict[str, Any]] = []
    for conn in _CONNECTORS:
        state_doc: dict[str, Any] | None = await db["sync_state"].find_one(  # type: ignore[func-returns-value]
            {"_id": conn["id"]}
        )
        state, count = _derive_state(live.get(conn["id"]), state_doc)
        statuses.append({
            "connector": conn["id"],
            "product": conn["product"],
            "deployment": conn["deployment"],
            "cursor": state_doc.get("cursor") if state_doc else None,
            "last_success_at": (
                state_doc.get("last_success_at") if state_doc else None
            ),
            "last_error": state_doc.get("last_error") if state_doc else None,
            "note": conn.get("note"),
            "state": state,
            "count": count,
        })

    return {
        "running": snap["running"],
        "cancelled": snap["cancelled"],
        "started_at": snap["started_at"],
        "finished_at": snap["finished_at"],
        "connectors": statuses,
    }
