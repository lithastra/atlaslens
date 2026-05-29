import csv
import hashlib
import io
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from atlaslens.api.deps import get_current_user, get_database

router = APIRouter(tags=["exports"])

DB = Annotated[
    AsyncIOMotorDatabase, Depends(get_database)
]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]

_CSV_FIELDS = [
    "id",
    "occurred_at",
    "product",
    "deployment",
    "pipeline",
    "actor_id",
    "actor_display_name",
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
    "actor_display_name",
    "operation",
    "category",
    "severity",
    "object_type",
    "object_ref_name",
    "source_ip",
]

# Friendlier PDF column headers than the auto-titled field names.
_PDF_HEADERS = {
    "occurred_at": "Time (UTC)",
    "actor_display_name": "User",
    "object_type": "Type",
    "object_ref_name": "Title",
    "source_ip": "Source IP",
}


async def _build_match(
    product: list[str] | None,
    category: str | None,
    severity: str | None,
    pipeline: str | None,
    operation: str | None,
    actor: str | None,
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
    return match


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
    fmt: str = Query("csv", alias="format"),
) -> StreamingResponse:
    match = await _build_match(
        product, category, severity, pipeline,
        operation, actor, date_from, date_to,
    )

    cursor = (
        db["events"]
        .find(match, {"raw": 0})
        .sort("occurred_at", -1)
    )
    rows: list[dict[str, str]] = []
    hasher = hashlib.sha256()
    doc: dict[str, Any]
    async for doc in cursor:
        rows.append(_flatten(doc))
        hasher.update(str(doc["_id"]).encode())

    await _resolve_display_names(db, rows)

    generated_at = datetime.now(UTC).isoformat()

    if fmt == "pdf":
        return _render_pdf(rows, hasher.hexdigest(), generated_at)

    return _render_csv(rows, match, hasher.hexdigest(), generated_at)


def _render_csv(
    rows: list[dict[str, str]],
    match: dict[str, Any],
    digest: str,
    generated_at: str,
) -> StreamingResponse:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDS)
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

    integrity_line = (
        f"\n# Integrity: count={len(rows)} "
        f"sha256={digest} "
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


def _render_pdf(
    rows: list[dict[str, str]],
    digest: str,
    generated_at: str,
) -> StreamingResponse:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )
    styles = getSampleStyleSheet()
    elements: list[Any] = []

    elements.append(Paragraph("AtlasLens Export", styles["Title"]))
    elements.append(Paragraph(
        f"Generated: {generated_at} | "
        f"Records: {len(rows)} | "
        f"SHA-256: {digest[:16]}...",
        styles["Normal"],
    ))
    elements.append(Spacer(1, 8 * mm))

    header = [
        _PDF_HEADERS.get(c, c.replace("_", " ").title())
        for c in _PDF_COLUMNS
    ]
    table_data: list[list[str]] = [header]
    for row in rows:
        table_data.append([
            _truncate(row.get(c, ""), 30) for c in _PDF_COLUMNS
        ])

    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a1a2e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.whitesmoke, colors.white,
        ]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(table)

    doc.build(elements)
    buf.seek(0)
    filename = f"atlaslens_export_{generated_at[:10]}.pdf"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )


def _truncate(s: str, max_len: int) -> str:
    s = s or ""
    return s if len(s) <= max_len else s[: max_len - 1] + "…"


async def _resolve_display_names(
    db: AsyncIOMotorDatabase,
    rows: list[dict[str, str]],
) -> None:
    """Fill actor_display_name from the identities collection.

    actor_raw is an opaque accountId; the human-readable name lives on
    the resolved identity. Falls back to "" when unresolved.
    """
    actor_ids = {r["actor_id"] for r in rows if r.get("actor_id")}
    if not actor_ids:
        return
    name_map: dict[str, str] = {}
    doc: dict[str, Any]
    async for doc in db["identities"].find(
        {"_id": {"$in": list(actor_ids)}},
        {"display_name": 1},
    ):
        if doc.get("display_name"):
            name_map[doc["_id"]] = doc["display_name"]
    for row in rows:
        aid = row.get("actor_id")
        if aid and aid in name_map:
            row["actor_display_name"] = name_map[aid]


def _flatten(doc: dict[str, Any]) -> dict[str, str]:
    obj_ref = doc.get("object_ref") or {}
    occurred = doc.get("occurred_at", "")
    if isinstance(occurred, datetime):
        occurred = occurred.isoformat()

    flat: dict[str, Any] = {
        "id": doc.get("_id", ""),
        "occurred_at": occurred,
        "product": doc.get("product", ""),
        "deployment": doc.get("deployment", ""),
        "pipeline": doc.get("pipeline", ""),
        "actor_id": doc.get("actor_id", ""),
        "actor_display_name": "",
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
    # Nullable fields (source_ip, container, unresolved actor_id) come
    # back as None; coerce so csv/pdf rendering never sees a None.
    return {k: ("" if v is None else str(v)) for k, v in flat.items()}
