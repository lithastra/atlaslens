import csv
import hashlib
import io
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from atlaslens.config import settings

logger = logging.getLogger(__name__)

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

_PDF_COLUMNS = [
    "occurred_at",
    "product",
    "actor_raw",
    "operation",
    "category",
    "severity",
    "object_type",
    "object_ref_name",
    "source_ip",
]


async def generate_report(
    db: AsyncIOMotorDatabase,
    report_def: dict[str, Any],
) -> str:
    match = _build_match(report_def.get("filters", {}))

    cursor = db["events"].find(match, {"raw": 0}).sort("occurred_at", -1)
    rows: list[dict[str, str]] = []
    hasher = hashlib.sha256()
    doc: dict[str, Any]
    async for doc in cursor:
        rows.append(_flatten(doc))
        hasher.update(str(doc["_id"]).encode())

    generated_at = datetime.now(UTC).isoformat()
    digest = hasher.hexdigest()
    fmt = report_def.get("format", "csv")

    output_dir = Path(settings.report_output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    name_slug = report_def.get("name", "report").replace(" ", "_").lower()
    date_slug = generated_at[:10]

    if fmt == "pdf":
        path = output_dir / f"{name_slug}_{date_slug}.pdf"
        _write_pdf(path, rows, digest, generated_at)
    else:
        path = output_dir / f"{name_slug}_{date_slug}.csv"
        _write_csv(path, rows, match, digest, generated_at)

    await db["scheduled_reports"].update_one(
        {"_id": report_def["_id"]},
        {
            "$set": {
                "last_run_at": datetime.now(UTC),
                "last_output": str(path),
                "last_count": len(rows),
            }
        },
    )

    logger.info(
        "Report '%s' generated: %d rows -> %s",
        report_def.get("name"),
        len(rows),
        path,
    )
    return str(path)


async def run_scheduled_reports(db: AsyncIOMotorDatabase) -> int:
    now = datetime.now(UTC)
    count = 0
    doc: dict[str, Any]
    async for doc in db["scheduled_reports"].find({"enabled": True}):
        last_run: datetime | None = doc.get("last_run_at")
        schedule: str = doc.get("schedule", "monthly")

        if last_run and not _is_due(last_run, schedule, now):
            continue

        try:
            await generate_report(db, doc)
            count += 1
        except Exception:
            logger.exception("Failed to generate report '%s'", doc.get("name"))

    return count


def _is_due(last_run: datetime, schedule: str, now: datetime) -> bool:
    delta = now - last_run
    if schedule == "daily":
        return delta.days >= 1
    if schedule == "weekly":
        return delta.days >= 7
    return delta.days >= 28


def _build_match(filters: dict[str, Any]) -> dict[str, Any]:
    match: dict[str, Any] = {}
    if filters.get("product"):
        products = filters["product"]
        match["product"] = (
            {"$in": products} if isinstance(products, list) else products
        )
    if filters.get("category"):
        match["category"] = filters["category"]
    if filters.get("severity"):
        match["severity"] = filters["severity"]
    if filters.get("pipeline"):
        match["pipeline"] = filters["pipeline"]
    return match


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


def _write_csv(
    path: Path,
    rows: list[dict[str, str]],
    match: dict[str, Any],
    digest: str,
    generated_at: str,
) -> None:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDS)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    buf.write(
        f"\n# Integrity: count={len(rows)} "
        f"sha256={digest} "
        f"generated_at={generated_at} "
        f"filter={match}"
    )
    path.write_text(buf.getvalue())


def _write_pdf(
    path: Path,
    rows: list[dict[str, str]],
    digest: str,
    generated_at: str,
) -> None:
    doc = SimpleDocTemplate(
        str(path),
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    elements: list[Any] = []

    elements.append(Paragraph("AtlasLens Scheduled Report", styles["Title"]))
    elements.append(
        Paragraph(
            f"Generated: {generated_at} | "
            f"Records: {len(rows)} | "
            f"SHA-256: {digest[:16]}...",
            styles["Normal"],
        )
    )
    elements.append(Spacer(1, 8 * mm))

    header = [c.replace("_", " ").title() for c in _PDF_COLUMNS]
    table_data: list[list[str]] = [header]
    for row in rows:
        s = row.get
        table_data.append([
            _trunc(s(c, ""), 30) for c in _PDF_COLUMNS
        ])

    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTSIZE", (0, 1), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                colors.whitesmoke,
                colors.white,
            ]),
        ])
    )
    elements.append(table)
    doc.build(elements)


def _trunc(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + "…"
