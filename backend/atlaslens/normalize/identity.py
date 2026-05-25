import logging
import uuid
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from atlaslens.normalize.crypto import encrypt_field

logger = logging.getLogger(__name__)


async def resolve_identity(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    actor_raw: str,
    deployment: str,
    product: str,
    display_name: str = "",
    email: str = "",
) -> str | None:
    """Look up or create a canonical identity for an actor_raw value."""
    if not actor_raw:
        return None

    col = db["identities"]
    doc: dict[str, Any] | None = await col.find_one(
        {"accounts.external_id": actor_raw}
    )

    if doc:
        identity_id: str = doc["_id"]

        has_link = any(
            a["external_id"] == actor_raw
            and a["deployment"] == deployment
            and a["product"] == product
            for a in doc.get("accounts", [])
        )
        if not has_link:
            await col.update_one(
                {"_id": identity_id},
                {
                    "$addToSet": {
                        "accounts": {
                            "deployment": deployment,
                            "product": product,
                            "external_id": actor_raw,
                        }
                    }
                },
            )

        if display_name and not doc.get("display_name"):
            await col.update_one(
                {"_id": identity_id},
                {"$set": {"display_name": display_name}},
            )
        return identity_id

    identity_id = f"person:{uuid.uuid4().hex[:12]}"
    encrypted_emails = [encrypt_field(email)] if email else []

    await col.insert_one(
        {
            "_id": identity_id,
            "display_name": display_name,
            "emails": encrypted_emails,
            "accounts": [
                {
                    "deployment": deployment,
                    "product": product,
                    "external_id": actor_raw,
                }
            ],
        }
    )
    logger.info(
        "created identity %s for %s (%s/%s)",
        identity_id,
        actor_raw,
        deployment,
        product,
    )
    return identity_id


async def backfill_actor_ids(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
    batch_size: int = 500,
) -> int:
    """Set actor_id on events that have actor_raw but no actor_id."""
    events = db["events"]
    updated = 0
    cursor = events.find(
        {"actor_raw": {"$ne": ""}, "actor_id": None},
        {"actor_raw": 1, "deployment": 1, "product": 1},
    ).batch_size(batch_size)

    async for doc in cursor:
        actor_id = await resolve_identity(
            db,
            doc["actor_raw"],
            doc["deployment"],
            doc["product"],
        )
        if actor_id:
            await events.update_one(
                {"_id": doc["_id"]},
                {"$set": {"actor_id": actor_id}},
            )
            updated += 1

    logger.info("backfill_actor_ids: updated %d events", updated)
    return updated
