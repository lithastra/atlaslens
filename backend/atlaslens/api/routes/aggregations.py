from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from atlaslens.api.deps import get_current_user, get_database

router = APIRouter(prefix="/aggregations", tags=["aggregations"])

DB = Annotated[
    AsyncIOMotorDatabase, Depends(get_database)
]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


@router.get("/timeseries")
async def timeseries(
    db: DB,
    _user: CurrentUser,
    granularity: str = Query("day", pattern="^(day|week)$"),
    group_by: str = Query("category", pattern="^(category|product|operation)$"),
    product: Annotated[list[str] | None, Query()] = None,
    category: str | None = None,
    severity: str | None = None,
    pipeline: str | None = None,
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
) -> list[dict[str, Any]]:
    match = _match_stage(
        product=product,
        category=category,
        severity=severity,
        pipeline=pipeline,
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
    category: str | None = None,
    severity: str | None = None,
    pipeline: str | None = None,
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
) -> list[dict[str, Any]]:
    match = _match_stage(
        product=product,
        category=category,
        severity=severity,
        pipeline=pipeline,
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
    category: str | None = None,
    severity: str | None = None,
    pipeline: str | None = None,
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
) -> dict[str, Any]:
    match = _match_stage(
        product=product,
        category=category,
        severity=severity,
        pipeline=pipeline,
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


def _match_stage(
    *,
    product: list[str] | None,
    category: str | None,
    severity: str | None,
    pipeline: str | None,
    date_from: str | None,
    date_to: str | None,
) -> dict[str, Any]:
    match: dict[str, Any] = {}
    if product:
        match["product"] = (
            {"$in": product} if len(product) > 1 else product[0]
        )
    if category:
        match["category"] = category
    if severity:
        match["severity"] = severity
    if pipeline:
        match["pipeline"] = pipeline
    if date_from or date_to:
        d: dict[str, Any] = {}
        if date_from:
            d["$gte"] = datetime.fromisoformat(date_from)
        if date_to:
            d["$lte"] = datetime.fromisoformat(date_to)
        if d:
            match["occurred_at"] = d
    return match
