import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from atlaslens.api.deps import get_current_user, get_database

router = APIRouter(prefix="/reports", tags=["reports"])

DB = Annotated[AsyncIOMotorDatabase, Depends(get_database)]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


class ScheduleRequest(BaseModel):
    name: str
    schedule: str = "monthly"
    format: str = "csv"
    filters: dict[str, Any] = {}


@router.post("/scheduled")
async def create_scheduled_report(
    db: DB,
    _user: CurrentUser,
    body: ScheduleRequest,
) -> dict[str, Any]:
    doc_id = f"report:{uuid.uuid4().hex[:12]}"
    doc = {
        "_id": doc_id,
        "name": body.name,
        "schedule": body.schedule,
        "format": body.format,
        "filters": body.filters,
        "enabled": True,
        "created_at": datetime.now(UTC),
        "created_by": _user.get("username", ""),
        "last_run_at": None,
        "last_output": None,
        "last_count": None,
    }
    await db["scheduled_reports"].insert_one(doc)
    doc["id"] = doc.pop("_id")
    return doc


@router.get("/scheduled")
async def list_scheduled_reports(
    db: DB,
    _user: CurrentUser,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    doc: dict[str, Any]
    async for doc in db["scheduled_reports"].find().sort("created_at", -1):
        doc["id"] = doc.pop("_id")
        results.append(doc)
    return results


@router.delete("/scheduled/{report_id}")
async def delete_scheduled_report(
    db: DB,
    _user: CurrentUser,
    report_id: str,
) -> dict[str, str]:
    result = await db["scheduled_reports"].delete_one({"_id": report_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"status": "deleted"}
