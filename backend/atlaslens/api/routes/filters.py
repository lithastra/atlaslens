from typing import Annotated, Any

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from atlaslens.api.deps import get_current_user, get_database

router = APIRouter(tags=["filters"])

DB = Annotated[AsyncIOMotorDatabase, Depends(get_database)]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


@router.get("/filters")
async def get_filters(
    db: DB,
    _user: CurrentUser,
    group: str | None = None,
) -> dict[str, Any]:
    # When a group is selected, restrict the user list to its resolved
    # members so the User dropdown respects the chosen team.
    user_query: dict[str, Any] = {"display_name": {"$ne": ""}}
    if group:
        member_ids: list[str] = await db["group_membership"].distinct(
            "identity_id",
            {"canonical_group_id": group},
        )
        user_query["_id"] = {"$in": member_ids}

    users: list[dict[str, str]] = []
    doc: dict[str, Any]
    async for doc in db["identities"].find(
        user_query,
        {"display_name": 1},
    ).sort("display_name", 1):
        users.append({"id": doc["_id"], "name": doc["display_name"]})

    operations: list[str] = await db["events"].distinct("operation")
    operations.sort()

    # Only surface groups that have at least one resolved member, so the
    # dropdown stays useful (skips empty / customer-only org groups).
    member_group_ids: list[str] = await db[
        "group_membership"
    ].distinct("canonical_group_id")
    groups: list[dict[str, str]] = []
    async for doc in db["canonical_groups"].find(
        {"_id": {"$in": member_group_ids}},
        {"name": 1},
    ).sort("name", 1):
        groups.append({"id": doc["_id"], "name": doc["name"]})

    return {
        "users": users,
        "operations": operations,
        "groups": groups,
    }
