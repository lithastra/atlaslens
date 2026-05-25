import logging
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from atlaslens.connectors.base import Connector, Cursor
from atlaslens.normalize.identity import resolve_identity
from atlaslens.normalize.normalizer import normalize_event

logger = logging.getLogger(__name__)


async def run_connector(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    connector: Connector,
    pipeline: str,
) -> int:
    state_id = f"{connector.deployment}:{connector.product}:{pipeline}"
    cursor = await _load_cursor(db, state_id)

    try:
        raw_events = (
            await connector.fetch_audit(cursor)
            if pipeline == "audit"
            else await connector.fetch_activity(cursor)
        )

        count = 0
        latest_ts: datetime | None = None

        for raw in raw_events:
            event = normalize_event(
                raw, connector.product, connector.deployment, pipeline  # type: ignore[arg-type]
            )
            doc = event.to_doc()

            actor_id = await resolve_identity(
                db,
                event.actor_raw,
                event.deployment,
                event.product,
                display_name=_extract_display_name(
                    raw.payload, connector.product
                ),
            )
            if actor_id:
                doc["actor_id"] = actor_id

            await db["events"].replace_one(
                {"_id": doc["_id"]}, doc, upsert=True
            )
            count += 1

            if latest_ts is None or raw.occurred_at > latest_ts:
                latest_ts = raw.occurred_at

        new_cursor = (
            latest_ts.isoformat() if latest_ts else cursor
        )
        await _save_state(db, state_id, new_cursor)

        logger.info(
            "%s: upserted %d events, cursor=%s",
            state_id,
            count,
            new_cursor,
        )
        return count

    except Exception as exc:
        logger.error("%s: ingest failed: %s", state_id, exc)
        await db["sync_state"].update_one(
            {"_id": state_id},
            {"$set": {"last_error": str(exc)}},
            upsert=True,
        )
        raise


async def _load_cursor(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    state_id: str,
) -> Cursor:
    doc: dict[str, Any] | None = await db["sync_state"].find_one({"_id": state_id})
    if doc and doc.get("cursor"):
        return doc["cursor"]
    return None


async def _save_state(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    state_id: str,
    cursor: str | None,
) -> None:
    await db["sync_state"].replace_one(
        {"_id": state_id},
        {
            "_id": state_id,
            "cursor": cursor or "",
            "last_success_at": datetime.now(UTC),
            "last_error": None,
        },
        upsert=True,
    )


def _extract_display_name(
    payload: dict[str, Any], product: str
) -> str:
    if product in ("jira", "jsm"):
        fields = payload.get("fields") or {}
        creator = fields.get("creator") or {}
        if creator.get("displayName"):
            return creator["displayName"]
        author = payload.get("author") or {}
        if author.get("displayName"):
            return author["displayName"]
    elif product == "confluence":
        author = payload.get("author") or {}
        if author.get("displayName"):
            return author["displayName"]
    elif product == "bitbucket":
        author = payload.get("author") or {}
        if author.get("display_name"):
            return author["display_name"]
    return ""
