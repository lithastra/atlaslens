from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from atlaslens.api.deps import get_current_user, get_database

router = APIRouter(tags=["items"])

DB = Annotated[
    AsyncIOMotorDatabase, Depends(get_database)
]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


@router.get("/items")
async def list_items(
    db: DB,
    _user: CurrentUser,
    actor: str = Query(..., description="actor_id or actor_raw"),
    product: Annotated[list[str] | None, Query()] = None,
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
    sort: str = Query(
        "updated_desc",
        pattern="^(updated_desc|updated_asc|name)$",
    ),
    skip: int = 0,
    limit: int = Query(50, le=200),
) -> dict[str, Any]:
    match: dict[str, Any] = {
        "pipeline": "activity",
        "$or": [{"actor_id": actor}, {"actor_raw": actor}],
    }

    if product:
        match["product"] = (
            {"$in": product} if len(product) > 1 else product[0]
        )

    if date_from or date_to:
        d: dict[str, Any] = {}
        if date_from:
            d["$gte"] = datetime.fromisoformat(date_from)
        if date_to:
            d["$lte"] = datetime.fromisoformat(date_to)
        if d:
            match["occurred_at"] = d

    agg: list[dict[str, Any]] = [
        {"$match": match},
        {
            "$group": {
                "_id": {
                    "product": "$product",
                    "object_id": "$object_ref.id",
                },
                "name": {"$last": "$object_ref.name"},
                "container": {"$last": "$object_ref.container"},
                "object_type": {"$last": "$object_type"},
                "product": {"$last": "$product"},
                "updated_at": {"$max": "$occurred_at"},
                "created": {
                    "$sum": {
                        "$cond": [
                            {
                                "$in": [
                                    "$operation",
                                    [
                                        "issue_created",
                                        "page_created",
                                        "request_created",
                                    ],
                                ]
                            },
                            1,
                            0,
                        ]
                    }
                },
            }
        },
    ]

    sort_field: dict[str, int]
    if sort == "updated_asc":
        sort_field = {"updated_at": 1}
    elif sort == "name":
        sort_field = {"name": 1}
    else:
        sort_field = {"updated_at": -1}

    agg.extend([
        {"$sort": sort_field},
        {
            "$facet": {
                "total": [{"$count": "n"}],
                "items": [
                    {"$skip": skip},
                    {"$limit": limit},
                    {
                        "$project": {
                            "_id": 0,
                            "object_id": "$_id.object_id",
                            "product": 1,
                            "name": 1,
                            "container": 1,
                            "object_type": 1,
                            "updated_at": 1,
                            "role": {
                                "$cond": [
                                    {"$gt": ["$created", 0]},
                                    "created",
                                    "updated",
                                ]
                            },
                        }
                    },
                ],
            }
        },
    ])

    result: dict[str, Any] = {
        "items": [],
        "total": 0,
        "skip": skip,
        "limit": limit,
    }
    doc: dict[str, Any]
    async for doc in db["events"].aggregate(agg):  # type: ignore[attr-defined]
        total_list = doc.get("total", [])
        result["total"] = (
            total_list[0]["n"] if total_list else 0
        )
        for item in doc.get("items", []):
            ts = item.get("updated_at")
            if isinstance(ts, datetime):
                item["updated_at"] = ts.isoformat()
            result["items"].append(item)

    return result
