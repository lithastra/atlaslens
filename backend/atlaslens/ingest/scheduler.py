import logging

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from atlaslens.config import settings
from atlaslens.connectors.cloud.bitbucket import BitbucketCloudConnector
from atlaslens.connectors.cloud.confluence import ConfluenceCloudConnector
from atlaslens.connectors.cloud.jira import JiraCloudConnector
from atlaslens.connectors.cloud.jsm import JsmCloudConnector
from atlaslens.connectors.cloud.org_events import OrgEventsConnector
from atlaslens.ingest.runner import run_connector

logger = logging.getLogger(__name__)


async def run_all_audit(
    db: AsyncIOMotorDatabase,  # type: ignore[type-arg]
) -> dict[str, int | str]:
    results: dict[str, int | str] = {}
    base = f"https://{settings.atlassian_site}.atlassian.net"
    auth = (settings.atlassian_email, settings.atlassian_api_token)

    async with httpx.AsyncClient() as client:
        connectors: list[tuple[str, object]] = []

        if settings.atlassian_site and settings.atlassian_api_token:
            connectors.extend([
                ("jira:audit", JiraCloudConnector(base, auth, client)),
                (
                    "confluence:audit",
                    ConfluenceCloudConnector(base, auth, client),
                ),
                ("jsm:audit", JsmCloudConnector(base, auth, client)),
            ])

        if settings.atlassian_org_id:
            connectors.append((
                "org:audit",
                OrgEventsConnector(
                    settings.atlassian_org_id,
                    settings.atlassian_api_token,
                    client,
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
