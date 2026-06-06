from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from atlaslens.api.deps import get_current_user, get_database
from atlaslens.api.routes.events import (
    _build_filter,
    _resolve_group_members,
)

router = APIRouter(prefix="/aggregations", tags=["aggregations"])

DB = Annotated[
    AsyncIOMotorDatabase, Depends(get_database)
]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


async def _agg_match(
    db: AsyncIOMotorDatabase,
    *,
    product: list[str] | None = None,
    deployment: list[str] | None = None,
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
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict[str, Any]:
    """Build the $match for an aggregation using the SAME filter logic as
    /events, so KPI/chart numbers honour every sidebar filter (actor, group,
    date drill-down, etc.) instead of just a subset.
    """
    match = _build_filter(
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
            match["actor_id"] = {"$in": member_ids}
    return match


@router.get("/timeseries")
async def timeseries(
    db: DB,
    _user: CurrentUser,
    granularity: str = Query("day", pattern="^(day|week)$"),
    group_by: str = Query("category", pattern="^(category|product|operation)$"),
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
) -> list[dict[str, Any]]:
    match = await _agg_match(
        db,
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
    )

    if granularity == "week":
        date_trunc = {
            "$dateTrunc": {
                "date": "$occurred_at",
                "unit": "week",
                "startOfWeek": "monday",
            }
        }
    else:
        date_trunc = {
            "$dateTrunc": {
                "date": "$occurred_at",
                "unit": "day",
            }
        }

    agg_pipeline: list[dict[str, Any]] = [
        {"$match": match},
        {
            "$group": {
                "_id": {
                    "bucket": date_trunc,
                    "group": f"${group_by}",
                },
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"_id.bucket": 1}},
        {
            "$project": {
                "_id": 0,
                "bucket": "$_id.bucket",
                "group": "$_id.group",
                "count": 1,
            }
        },
    ]

    results: list[dict[str, Any]] = []
    doc: dict[str, Any]
    async for doc in db["events"].aggregate(agg_pipeline):  # type: ignore[attr-defined]
        bucket = doc.get("bucket")
        if isinstance(bucket, datetime):
            doc["bucket"] = bucket.isoformat()
        results.append(doc)
    return results


@router.get("/top")
async def top(
    db: DB,
    _user: CurrentUser,
    field: str = Query(
        "actor",
        alias="field",
        pattern="^(actor|object|product|operation|project|space|repo)$",
    ),
    n: int = Query(10, alias="limit", le=50),
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
) -> list[dict[str, Any]]:
    match = await _agg_match(
        db,
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
    )

    field_map = {
        "actor": "$actor_id",
        "object": "$object_ref.name",
        "product": "$product",
        "operation": "$operation",
        "project": "$object_ref.container",
        "space": "$object_ref.container",
        "repo": "$object_ref.container",
    }
    group_field = field_map.get(field, "$actor_id")

    agg_pipeline: list[dict[str, Any]] = [
        {"$match": match},
        {
            "$group": {
                "_id": group_field,
                "count": {"$sum": 1},
            }
        },
        {"$sort": {"count": -1}},
        {"$limit": n},
    ]

    if field == "actor":
        agg_pipeline.append({
            "$lookup": {
                "from": "identities",
                "localField": "_id",
                "foreignField": "_id",
                "as": "_ident",
            }
        })
        agg_pipeline.append({
            "$project": {
                "_id": 0,
                "key": {
                    "$ifNull": [
                        {"$arrayElemAt": ["$_ident.display_name", 0]},
                        "$_id",
                    ]
                },
                "count": 1,
            }
        })
    else:
        agg_pipeline.append({
            "$project": {
                "_id": 0,
                "key": "$_id",
                "count": 1,
            }
        })

    results: list[dict[str, Any]] = []
    doc: dict[str, Any]
    async for doc in db["events"].aggregate(agg_pipeline):  # type: ignore[attr-defined]
        results.append(doc)
    return results


@router.get("/summary")
async def summary(
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
) -> dict[str, Any]:
    match = await _agg_match(
        db,
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
    )

    agg_pipeline: list[dict[str, Any]] = [
        {"$match": match},
        {
            "$facet": {
                "total": [{"$count": "n"}],
                "by_product": [
                    {
                        "$group": {
                            "_id": "$product",
                            "count": {"$sum": 1},
                        }
                    }
                ],
                "by_category": [
                    {
                        "$group": {
                            "_id": "$category",
                            "count": {"$sum": 1},
                        }
                    }
                ],
                "by_severity": [
                    {
                        "$group": {
                            "_id": "$severity",
                            "count": {"$sum": 1},
                        }
                    }
                ],
                "unique_actors": [
                    {"$group": {"_id": "$actor_id"}},
                    {"$count": "n"},
                ],
            }
        },
    ]

    result: dict[str, Any] = {}
    doc: dict[str, Any]
    async for doc in db["events"].aggregate(agg_pipeline):  # type: ignore[attr-defined]
        total_list = doc.get("total", [])
        result["total_events"] = (
            total_list[0]["n"] if total_list else 0
        )
        result["by_product"] = {
            r["_id"]: r["count"]
            for r in doc.get("by_product", [])
        }
        result["by_category"] = {
            r["_id"]: r["count"]
            for r in doc.get("by_category", [])
        }
        result["by_severity"] = {
            r["_id"]: r["count"]
            for r in doc.get("by_severity", [])
        }
        actors_list = doc.get("unique_actors", [])
        result["unique_actors"] = (
            actors_list[0]["n"] if actors_list else 0
        )
    return result


