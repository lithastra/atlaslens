from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from atlaslens.api.deps import get_current_user, get_database

router = APIRouter(tags=["events"])

DB = Annotated[
    AsyncIOMotorDatabase, Depends(get_database)
]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


@router.get("/events")
async def list_events(
    db: DB,
    _user: CurrentUser,
    product: Annotated[list[str] | None, Query()] = None,
    deployment: Annotated[list[str] | None, Query()] = None,
    actor: str | None = None,
    group: str | None = None,
    operation: str | None = None,
    category: str | None = None,
    severity: str | None = None,
    object_type: str | None = None,
    pipeline: str | None = None,
    q: str | None = None,
    year: int | None = None,
    month: int | None = None,
    day: int | None = None,
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    skip: int = 0,
    limit: int = Query(50, le=500),
) -> dict[str, Any]:
    filter = _build_filter(
        product=product,
        deployment=deployment,
        actor=actor,
        group=group,
        operation=operation,
        category=category,
        severity=severity,
        object_type=object_type,
        pipeline=pipeline,
        q=q,
        year=year,
        month=month,
        day=day,
        date_from=date_from,
        date_to=date_to,
        db=db,
    )

    if group:
        member_ids = await _resolve_group_members(db, group)
        if member_ids is not None:
            filter["actor_id"] = {"$in": member_ids}

    col = db["events"]
    total = await col.count_documents(filter)
    cursor = (
        col.find(filter, {"raw": 0})
        .sort("occurred_at", -1)
        .skip(skip)
        .limit(limit)
    )
    items: list[dict[str, Any]] = []
    doc: dict[str, Any]
    async for doc in cursor:
        items.append(_serialize(doc))

    await _resolve_actor_names(db, items)

    return {
        "items": items,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/events/{event_id:path}")
async def get_event(
    event_id: str,
    db: DB,
    _user: CurrentUser,
) -> dict[str, Any]:
    doc: dict[str, Any] | None = await db["events"].find_one({"_id": event_id})  # type: ignore[func-returns-value]
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event not found",
        )
    return _serialize(doc)


def _build_filter(
    *,
    product: list[str] | None,
    deployment: list[str] | None,
    actor: str | None,
    group: str | None,
    operation: str | None,
    category: str | None,
    severity: str | None,
    object_type: str | None,
    pipeline: str | None,
    q: str | None,
    year: int | None,
    month: int | None,
    day: int | None,
    date_from: str | None,
    date_to: str | None,
    db: Any = None,
) -> dict[str, Any]:
    f: dict[str, Any] = {}

    if product:
        f["product"] = (
            {"$in": product} if len(product) > 1 else product[0]
        )
    if deployment:
        f["deployment"] = (
            {"$in": deployment}
            if len(deployment) > 1
            else deployment[0]
        )
    if actor:
        f["$or"] = [
            {"actor_id": actor},
            {"actor_raw": actor},
        ]
    if operation:
        f["operation"] = operation
    if category:
        f["category"] = category
    if severity:
        f["severity"] = severity
    if object_type:
        f["object_type"] = object_type
    if pipeline:
        f["pipeline"] = pipeline
    if q:
        f["$text"] = {"$search": q}

    date_filter = _build_date_filter(
        year=year,
        month=month,
        day=day,
        date_from=date_from,
        date_to=date_to,
    )
    if date_filter:
        f["occurred_at"] = date_filter

    return f


def _build_date_filter(
    *,
    year: int | None,
    month: int | None,
    day: int | None,
    date_from: str | None,
    date_to: str | None,
) -> dict[str, Any] | None:
    if date_from or date_to:
        d: dict[str, Any] = {}
        if date_from:
            d["$gte"] = datetime.fromisoformat(date_from)
        if date_to:
            d["$lte"] = datetime.fromisoformat(date_to)
        return d if d else None

    if year:
        start = datetime(year, month or 1, day or 1, tzinfo=UTC)
        if day:
            end = datetime(
                year, month or 1, day, 23, 59, 59, tzinfo=UTC
            )
        elif month:
            next_month = month + 1
            next_year = year
            if next_month > 12:
                next_month = 1
                next_year += 1
            end = datetime(next_year, next_month, 1, tzinfo=UTC)
        else:
            end = datetime(year + 1, 1, 1, tzinfo=UTC)
        return {"$gte": start, "$lt": end}

    return None


async def _resolve_group_members(
    db: AsyncIOMotorDatabase,
    group: str,
) -> list[str] | None:
    docs = db["group_membership"].find(
        {"canonical_group_id": group},
        {"identity_id": 1},
    )
    ids: list[str] = []
    d: dict[str, Any]
    async for d in docs:
        ids.append(d["identity_id"])
    return ids if ids else None


async def _resolve_actor_names(
    db: AsyncIOMotorDatabase,
    items: list[dict[str, Any]],
) -> None:
    actor_ids = {
        item["actor_id"]
        for item in items
        if item.get("actor_id")
    }
    if not actor_ids:
        return
    name_map: dict[str, str] = {}
    doc: dict[str, Any]
    async for doc in db["identities"].find(  # type: ignore[attr-defined]
        {"_id": {"$in": list(actor_ids)}},
        {"display_name": 1},
    ):
        if doc.get("display_name"):
            name_map[doc["_id"]] = doc["display_name"]
    for item in items:
        aid = item.get("actor_id")
        if aid and aid in name_map:
            item["actor_display_name"] = name_map[aid]


def _serialize(doc: dict[str, Any]) -> dict[str, Any]:
    doc["id"] = doc.pop("_id")
    for key, val in doc.items():
        if isinstance(val, datetime):
            doc[key] = val.isoformat()
    return doc
