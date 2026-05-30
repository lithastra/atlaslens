import asyncio
import logging
from typing import Any

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from atlaslens.normalize.groups import (
    auto_map_groups,
    set_membership,
    upsert_canonical_group,
    upsert_source_group,
)

logger = logging.getLogger(__name__)

_PAGE = 50
_MAX_RETRIES = 3
_BACKOFF_BASE = 2.0


async def sync_groups(
    db: AsyncIOMotorDatabase,
    jira_base: str,
    auth: tuple[str, str],
    client: httpx.AsyncClient,
) -> dict[str, int]:
    """Pull Atlassian org groups + members into the group store.

    Each group becomes a source_group (namespace "atlassian-org") and a
    canonical_group; auto_map links them by name. Membership is recorded
    only for accountIds that already resolve to a known identity, so the
    user/group dimensions stay scoped to actually-audited people rather
    than every JSM customer.
    """
    base = jira_base.rstrip("/")
    groups = await _fetch_groups(base, auth, client)

    for group in groups:
        gid = group["groupId"]
        name = group["name"]
        await upsert_canonical_group(db, f"canon:{gid}", name)
        await upsert_source_group(db, "atlassian-org", gid, name)

    await auto_map_groups(db)

    memberships = 0
    for group in groups:
        gid = group["groupId"]
        canonical_id = f"canon:{gid}"
        for account_id in await _fetch_members(base, auth, client, gid):
            ident: dict[str, Any] | None = await db[  # type: ignore[func-returns-value]
                "identities"
            ].find_one({"accounts.external_id": account_id})
            if ident:
                await set_membership(db, canonical_id, ident["_id"])
                memberships += 1

    logger.info(
        "group sync: %d groups, %d memberships", len(groups), memberships
    )
    return {"groups": len(groups), "memberships": memberships}


async def _fetch_groups(
    base: str,
    auth: tuple[str, str],
    client: httpx.AsyncClient,
) -> list[dict[str, str]]:
    groups: list[dict[str, str]] = []
    start = 0
    while True:
        resp = await _request(
            client,
            f"{base}/rest/api/3/group/bulk",
            auth,
            params={"maxResults": _PAGE, "startAt": start},
        )
        data = resp.json()
        values: list[dict[str, Any]] = data.get("values", [])
        for v in values:
            gid = v.get("groupId")
            name = v.get("name")
            if gid and name:
                groups.append({"groupId": gid, "name": name})
        if data.get("isLast", True) or not values:
            break
        start += len(values)
    return groups


async def _fetch_members(
    base: str,
    auth: tuple[str, str],
    client: httpx.AsyncClient,
    group_id: str,
) -> list[str]:
    members: list[str] = []
    start = 0
    while True:
        resp = await _request(
            client,
            f"{base}/rest/api/3/group/member",
            auth,
            params={
                "groupId": group_id,
                "maxResults": _PAGE,
                "startAt": start,
            },
        )
        data = resp.json()
        values: list[dict[str, Any]] = data.get("values", [])
        for v in values:
            account_id = v.get("accountId")
            if account_id:
                members.append(account_id)
        if data.get("isLast", True) or not values:
            break
        start += len(values)
    return members


async def _request(
    client: httpx.AsyncClient,
    url: str,
    auth: tuple[str, str],
    params: dict[str, Any],
) -> httpx.Response:
    for attempt in range(_MAX_RETRIES):
        try:
            resp = await client.request(
                "GET",
                url,
                auth=auth,
                params=params,
                timeout=30.0,
            )
            if resp.status_code == 429:
                wait = float(
                    resp.headers.get(
                        "Retry-After", _BACKOFF_BASE ** (attempt + 1)
                    )
                )
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            return resp
        except httpx.TimeoutException:
            if attempt == _MAX_RETRIES - 1:
                raise
            await asyncio.sleep(_BACKOFF_BASE ** (attempt + 1))
    raise RuntimeError("max retries exceeded")
