import csv
import hashlib
import io
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase

from atlaslens.api.deps import get_current_user, get_database

router = APIRouter(tags=["exports"])

DB = Annotated[
    AsyncIOMotorDatabase, Depends(get_database)  # type: ignore[type-arg]
]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]

_CSV_FIELDS = [
    "id",
    "occurred_at",
    "product",
    "deployment",
    "pipeline",
    "actor_id",
    "actor_raw",
    "operation",
    "category",
    "severity",
    "object_type",
    "object_ref_id",
    "object_ref_name",
    "object_ref_container",
    "source_ip",
]


@router.post("/exports")
async def export_events(
    db: DB,
    _user: CurrentUser,
    product: Annotated[list[str] | None, Query()] = None,
    category: str | None = None,
    severity: str | None = None,
    pipeline: str | None = None,
    operation: str | None = None,
    actor: str | None = None,
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
) -> StreamingResponse:
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
    if operation:
        match["operation"] = operation
    if actor:
        match["$or"] = [
            {"actor_id": actor},
            {"actor_raw": actor},
        ]
    if date_from or date_to:
        d: dict[str, Any] = {}
        if date_from:
            d["$gte"] = datetime.fromisoformat(date_from)
        if date_to:
            d["$lte"] = datetime.fromisoformat(date_to)
        if d:
            match["occurred_at"] = d

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDS)
    writer.writeheader()

    hasher = hashlib.sha256()
    count = 0

    cursor = (
        db["events"]
        .find(match, {"raw": 0})
        .sort("occurred_at", -1)
    )
    async for doc in cursor:
        row = _flatten(doc)
        writer.writerow(row)
        hasher.update(str(doc["_id"]).encode())
        count += 1

    generated_at = datetime.now(UTC).isoformat()
    integrity_line = (
        f"\n# Integrity: count={count} "
        f"sha256={hasher.hexdigest()} "
        f"generated_at={generated_at} "
        f"filter={match}"
    )
    buf.write(integrity_line)

    buf.seek(0)
    filename = f"atlaslens_export_{generated_at[:10]}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


def _flatten(doc: dict[str, Any]) -> dict[str, str]:
    obj_ref = doc.get("object_ref") or {}
    occurred = doc.get("occurred_at", "")
    if isinstance(occurred, datetime):
        occurred = occurred.isoformat()

    return {
        "id": doc.get("_id", ""),
        "occurred_at": occurred,
        "product": doc.get("product", ""),
        "deployment": doc.get("deployment", ""),
        "pipeline": doc.get("pipeline", ""),
        "actor_id": doc.get("actor_id", ""),
        "actor_raw": doc.get("actor_raw", ""),
        "operation": doc.get("operation", ""),
        "category": doc.get("category", ""),
        "severity": doc.get("severity", ""),
        "object_type": doc.get("object_type", ""),
        "object_ref_id": obj_ref.get("id", ""),
        "object_ref_name": obj_ref.get("name", ""),
        "object_ref_container": obj_ref.get("container", ""),
        "source_ip": doc.get("source_ip", ""),
    }
