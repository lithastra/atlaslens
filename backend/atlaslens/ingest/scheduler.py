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
from atlaslens.connectors.cloud.org_events import OrgEventsConnector
from atlaslens.connectors.rate_budget import RateBudget
from atlaslens.ingest.runner import run_connector

logger = logging.getLogger(__name__)


async def run_all_audit(
    db: AsyncIOMotorDatabase,
) -> dict[str, int | str]:
    results: dict[str, int | str] = {}
    base = f"https://{settings.atlassian_site}.atlassian.net"
    auth = (settings.atlassian_email, settings.atlassian_api_token)

    budget = RateBudget(max_requests_per_minute=30, max_requests_per_cycle=500)
    org_budget = RateBudget(max_requests_per_minute=8, max_requests_per_cycle=100)

    async with httpx.AsyncClient() as client:
        connectors: list[tuple[str, object]] = []

        if settings.atlassian_site and settings.atlassian_api_token:
            connectors.extend([
                ("jira:audit", JiraCloudConnector(base, auth, client, budget)),
                (
                    "confluence:audit",
                    ConfluenceCloudConnector(base, auth, client, budget),
                ),
                ("jsm:audit", JsmCloudConnector(base, auth, client, budget)),
            ])

        if settings.atlassian_org_id:
            connectors.append((
                "org:audit",
                OrgEventsConnector(
                    settings.atlassian_org_id,
                    settings.atlassian_api_token,
                    client,
                    org_budget,
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
    base = f"https://{settings.atlassian_site}.atlassian.net"
    auth = (settings.atlassian_email, settings.atlassian_api_token)
    budget = RateBudget(max_requests_per_minute=30, max_requests_per_cycle=500)

    async with httpx.AsyncClient() as client:
        connectors: list[tuple[str, object]] = []

        if settings.atlassian_site and settings.atlassian_api_token:
            connectors.extend([
                (
                    "jira:activity",
                    JiraActivityConnector(base, auth, client, budget),
                ),
                (
                    "confluence:activity",
                    ConfluenceActivityConnector(
                        base, auth, client, budget
                    ),
                ),
                (
                    "jsm:activity",
                    JsmActivityConnector(base, auth, client, budget=budget),
                ),
            ])

        if settings.bitbucket_workspace and settings.bitbucket_app_password:
            bb_auth = (
                settings.atlassian_email,
                settings.bitbucket_app_password,
            )
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


async def run_all(
    db: AsyncIOMotorDatabase,
) -> dict[str, int | str]:
    results: dict[str, int | str] = {}
    results.update(await run_all_audit(db))
    results.update(await run_all_activity(db))
    return results
