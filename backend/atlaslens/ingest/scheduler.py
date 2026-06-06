import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from atlaslens.config import settings
from atlaslens.connectors.cloud.bitbucket import BitbucketCloudConnector
from atlaslens.connectors.cloud.bitbucket_activity import BitbucketActivityConnector
from atlaslens.connectors.cloud.confluence import ConfluenceCloudConnector
from atlaslens.connectors.cloud.confluence_activity import ConfluenceActivityConnector
from atlaslens.connectors.cloud.jira import JiraCloudConnector
from atlaslens.connectors.cloud.jira_activity import JiraActivityConnector
from atlaslens.connectors.cloud.jsm import JsmCloudConnector
from atlaslens.connectors.cloud.jsm_activity import JsmActivityConnector
from atlaslens.connectors.rate_budget import RateBudget
from atlaslens.ingest.group_sync import sync_groups
from atlaslens.ingest.runner import run_connector

logger = logging.getLogger(__name__)

# Synthetic connector id for the org group/membership sync (shares the
# sync_state collection so its "last sync" persists like any connector).
GROUPS_ID = "cloud:atlassian-org:groups"

# Progress callback: report(connector_id, state, *, count=?, error=?)
ReportFn = Callable[..., None]


def _noop_report(*_args: Any, **_kwargs: Any) -> None:
    pass


async def run_all_audit(
    db: AsyncIOMotorDatabase,
    report: ReportFn = _noop_report,
) -> dict[str, int | str]:
    results: dict[str, int | str] = {}
    cloud_id = settings.atlassian_cloud_id
    jira_base = f"https://api.atlassian.com/ex/jira/{cloud_id}"
    confluence_base = f"https://api.atlassian.com/ex/confluence/{cloud_id}"

    budget = RateBudget(max_requests_per_minute=30, max_requests_per_cycle=500)

    async with httpx.AsyncClient() as client:
        connectors: list[tuple[str, object]] = []

        if cloud_id and settings.jira_api_token:
            jira_auth = (settings.atlassian_email, settings.jira_api_token)
            # Jira audit-log endpoint also backs JSM; jira:audit excludes
            # JSM-sourced records and jsm:audit ingests only those.
            connectors.append((
                "jira:audit",
                JiraCloudConnector(jira_base, jira_auth, client, budget),
            ))
            connectors.append((
                "jsm:audit",
                JsmCloudConnector(jira_base, jira_auth, client, budget),
            ))

        if cloud_id and settings.confluence_api_token:
            confluence_auth = (
                settings.atlassian_email,
                settings.confluence_api_token,
            )
            connectors.append((
                "confluence:audit",
                ConfluenceCloudConnector(
                    confluence_base, confluence_auth, client, budget
                ),
            ))

        connectors.append(("bitbucket:audit", BitbucketCloudConnector()))

        for label, _connector in connectors:
            report(f"cloud:{label}", "pending")
        for label, connector in connectors:
            cid = f"cloud:{label}"
            report(cid, "running")
            try:
                count = await run_connector(
                    db, connector, "audit"  # type: ignore[arg-type]
                )
                results[label] = count
                report(cid, "done", count=count)
            except Exception as exc:
                logger.error("%s failed: %s", label, exc)
                results[label] = f"error: {exc}"
                report(cid, "error", error=str(exc))

    return results


async def run_all_activity(
    db: AsyncIOMotorDatabase,
    report: ReportFn = _noop_report,
) -> dict[str, int | str]:
    results: dict[str, int | str] = {}
    cloud_id = settings.atlassian_cloud_id
    jira_base = f"https://api.atlassian.com/ex/jira/{cloud_id}"
    confluence_base = f"https://api.atlassian.com/ex/confluence/{cloud_id}"
    budget = RateBudget(max_requests_per_minute=30, max_requests_per_cycle=500)

    async with httpx.AsyncClient() as client:
        connectors: list[tuple[str, object]] = []

        if cloud_id and settings.jira_api_token:
            jira_auth = (settings.atlassian_email, settings.jira_api_token)
            connectors.extend([
                (
                    "jira:activity",
                    JiraActivityConnector(jira_base, jira_auth, client, budget),
                ),
                (
                    "jsm:activity",
                    JsmActivityConnector(jira_base, jira_auth, client, budget=budget),
                ),
            ])

        if cloud_id and settings.confluence_api_token:
            confluence_auth = (settings.atlassian_email, settings.confluence_api_token)
            connectors.append((
                "confluence:activity",
                ConfluenceActivityConnector(
                    confluence_base, confluence_auth, client, budget
                ),
            ))

        if settings.bitbucket_workspace and settings.bitbucket_api_token:
            bb_auth = (settings.atlassian_email, settings.bitbucket_api_token)
            bb_budget = RateBudget(
                max_requests_per_minute=30, max_requests_per_cycle=500
            )
            connectors.append((
                "bitbucket:activity",
                BitbucketActivityConnector(
                    settings.bitbucket_workspace,
                    bb_auth,
                    client,
                    budget=bb_budget,
                ),
            ))

        for label, _connector in connectors:
            report(f"cloud:{label}", "pending")
        for label, connector in connectors:
            cid = f"cloud:{label}"
            report(cid, "running")
            try:
                count = await run_connector(
                    db, connector, "activity"  # type: ignore[arg-type]
                )
                results[label] = count
                report(cid, "done", count=count)
            except Exception as exc:
                logger.error("%s failed: %s", label, exc)
                results[label] = f"error: {exc}"
                report(cid, "error", error=str(exc))

    return results


async def run_group_sync(
    db: AsyncIOMotorDatabase,
    report: ReportFn = _noop_report,
) -> dict[str, int | str]:
    cloud_id = settings.atlassian_cloud_id
    if not (cloud_id and settings.jira_api_token):
        return {}
    report(GROUPS_ID, "running")
    jira_base = f"https://api.atlassian.com/ex/jira/{cloud_id}"
    auth = (settings.atlassian_email, settings.jira_api_token)
    async with httpx.AsyncClient() as client:
        try:
            res = await sync_groups(db, jira_base, auth, client)
            await db["sync_state"].replace_one(
                {"_id": GROUPS_ID},
                {
                    "_id": GROUPS_ID,
                    "cursor": "",
                    "last_success_at": datetime.now(UTC),
                    "last_error": None,
                },
                upsert=True,
            )
            report(GROUPS_ID, "done", count=res["memberships"])
            return {
                "groups:sync": res["groups"],
                "groups:memberships": res["memberships"],
            }
        except Exception as exc:
            logger.error("group sync failed: %s", exc)
            await db["sync_state"].update_one(
                {"_id": GROUPS_ID},
                {"$set": {"last_error": str(exc)}},
                upsert=True,
            )
            report(GROUPS_ID, "error", error=str(exc))
            return {"groups:sync": f"error: {exc}"}


async def run_all(
    db: AsyncIOMotorDatabase,
    report: ReportFn = _noop_report,
) -> dict[str, int | str]:
    results: dict[str, int | str] = {}
    results.update(await run_all_audit(db, report))
    results.update(await run_all_activity(db, report))
    results.update(await run_group_sync(db, report))
    return results
