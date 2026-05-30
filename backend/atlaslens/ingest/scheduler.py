import logging

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


async def run_all_audit(
    db: AsyncIOMotorDatabase,
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

        for label, connector in connectors:
            try:
                count = await run_connector(
                    db, connector, "audit"  # type: ignore[arg-type]
                )
                results[label] = count
            except Exception as exc:
                logger.error("%s failed: %s", label, exc)
                results[label] = f"error: {exc}"

    return results


async def run_all_activity(
    db: AsyncIOMotorDatabase,
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

        for label, connector in connectors:
            try:
                count = await run_connector(
                    db, connector, "activity"  # type: ignore[arg-type]
                )
                results[label] = count
            except Exception as exc:
                logger.error("%s failed: %s", label, exc)
                results[label] = f"error: {exc}"

    return results


async def run_group_sync(
    db: AsyncIOMotorDatabase,
) -> dict[str, int | str]:
    cloud_id = settings.atlassian_cloud_id
    if not (cloud_id and settings.jira_api_token):
        return {}
    jira_base = f"https://api.atlassian.com/ex/jira/{cloud_id}"
    auth = (settings.atlassian_email, settings.jira_api_token)
    async with httpx.AsyncClient() as client:
        try:
            res = await sync_groups(db, jira_base, auth, client)
            return {
                "groups:sync": res["groups"],
                "groups:memberships": res["memberships"],
            }
        except Exception as exc:
            logger.error("group sync failed: %s", exc)
            return {"groups:sync": f"error: {exc}"}


async def run_all(
    db: AsyncIOMotorDatabase,
) -> dict[str, int | str]:
    results: dict[str, int | str] = {}
    results.update(await run_all_audit(db))
    results.update(await run_all_activity(db))
    results.update(await run_group_sync(db))
    return results
