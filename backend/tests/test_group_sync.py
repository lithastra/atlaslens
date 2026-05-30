import httpx
import pytest

from atlaslens.ingest.group_sync import sync_groups
from tests.mock_db import MockDB

_GROUPS = {
    "maxResults": 50,
    "startAt": 0,
    "total": 2,
    "isLast": True,
    "values": [
        {"groupId": "g1", "name": "Engineering"},
        {"groupId": "g2", "name": "Empty Team"},
    ],
}

_MEMBERS = {
    "g1": {
        "maxResults": 50,
        "startAt": 0,
        "total": 2,
        "isLast": True,
        "values": [
            {"accountId": "acc1", "displayName": "Alice"},
            {"accountId": "unknown-acc", "displayName": "Ghost"},
        ],
    },
    "g2": {
        "maxResults": 50,
        "startAt": 0,
        "total": 0,
        "isLast": True,
        "values": [],
    },
}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith("/group/bulk"):
        return httpx.Response(200, json=_GROUPS)
    if path.endswith("/group/member"):
        gid = request.url.params.get("groupId", "")
        return httpx.Response(200, json=_MEMBERS.get(gid, _MEMBERS["g2"]))
    return httpx.Response(404)


class TestGroupSync:
    @pytest.mark.asyncio
    async def test_populates_groups_and_memberships(self) -> None:
        db = MockDB()
        # Only acc1 resolves to a known identity; the unknown member and
        # the empty group must not create memberships.
        await db["identities"].insert_one(
            {
                "_id": "person:1",
                "display_name": "Alice",
                "accounts": [{"external_id": "acc1"}],
            }
        )

        transport = httpx.MockTransport(_handler)
        async with httpx.AsyncClient(transport=transport) as client:
            result = await sync_groups(
                db,  # type: ignore[arg-type]
                "https://api.atlassian.com/ex/jira/cid",
                ("e@x.com", "tok"),
                client,
            )

        assert result == {"groups": 2, "memberships": 1}
        assert len(db["canonical_groups"].docs) == 2
        assert len(db["source_groups"].docs) == 2
        # Exactly one membership: canon:g1 <-> person:1
        memberships = db["group_membership"].docs
        assert list(memberships.keys()) == ["canon:g1:person:1"]
        assert memberships["canon:g1:person:1"]["identity_id"] == "person:1"
