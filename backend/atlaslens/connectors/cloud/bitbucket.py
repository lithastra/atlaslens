import logging

from atlaslens.connectors.base import Cursor, RawEvent
from atlaslens.models.event import Deployment, Product

logger = logging.getLogger(__name__)


class BitbucketCloudConnector:
    """Bitbucket Cloud connector.

    Audit: UNAVAILABLE — the Bitbucket Cloud audit-log API requires
    Atlassian Access/Guard, which is not licensed. This is a known gap
    surfaced in the dashboard rather than hidden.

    Activity: commits and PRs (implemented in the activity phase).
    """

    product: Product = "bitbucket"
    deployment: Deployment = "cloud"

    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def fetch_audit(self, cursor: Cursor) -> list[RawEvent]:
        logger.info(
            "bitbucket cloud audit: UNAVAILABLE (requires Guard)"
        )
        return []

    async def fetch_activity(self, cursor: Cursor) -> list[RawEvent]:
        return []
