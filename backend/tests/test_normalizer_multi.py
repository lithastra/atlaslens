from datetime import UTC, datetime

import pytest

from atlaslens.connectors.base import RawEvent
from atlaslens.normalize.normalizer import normalize_event


def _raw_confluence_audit(
    source_id: str = "200",
    summary: str = "Space permission changed",
) -> RawEvent:
    return RawEvent(
        source_id=source_id,
        occurred_at=datetime(2026, 4, 10, 8, 0, tzinfo=UTC),
        event_type=summary,
        payload={
            "id": int(source_id),
            "summary": summary,
            "remoteAddress": "10.0.0.1",
            "author": {"accountId": "conf-user-1"},
            "category": "permissions",
            "objectItem": {
                "id": "sp-1",
                "name": "Engineering",
                "typeName": "SPACE",
            },
            "changedValues": [],
        },
    )


def _raw_jsm_audit(
    source_id: str = "jsm-300",
    summary: str = "User added to group",
) -> RawEvent:
    return RawEvent(
        source_id=source_id,
        occurred_at=datetime(2026, 4, 12, 9, 0, tzinfo=UTC),
        event_type=summary,
        payload={
            "id": 300,
            "summary": summary,
            "remoteAddress": "172.16.0.1",
            "authorAccountId": "jsm-admin",
            "category": "group management",
            "eventSource": "Jira Service Management",
            "objectItem": {
                "id": "grp-5",
                "name": "sd-agents",
                "typeName": "GROUP",
            },
            "changedValues": [],
        },
    )


def _raw_org_event(
    source_id: str = "org-evt-1",
    action: str = "user_added_to_org",
) -> RawEvent:
    return RawEvent(
        source_id=source_id,
        occurred_at=datetime(2026, 4, 15, 12, 0, tzinfo=UTC),
        event_type=action,
        payload={
            "id": source_id,
            "attributes": {
                "action": action,
                "time": "2026-04-15T12:00:00Z",
                "actor": {"id": "admin-1"},
                "target": {"id": "user-99", "name": "bob"},
                "context": {"reason": "onboarding"},
                "location": {"ip": "203.0.113.5"},
            },
        },
    )


class TestConfluenceAuditNormalization:
    def test_permission_changed(self) -> None:
        event = normalize_event(
            _raw_confluence_audit(summary="Space permission changed"),
            "confluence",
            "cloud",
            "audit",
        )
        assert event.id == "cloud:confluence:200"
        assert event.product == "confluence"
        assert event.operation == "permission_changed"
        assert event.severity == "high"
        assert event.category == "security"

    def test_space_exported(self) -> None:
        event = normalize_event(
            _raw_confluence_audit(summary="Space export completed"),
            "confluence",
            "cloud",
            "audit",
        )
        assert event.operation == "data_exported"
        assert event.severity == "high"

    def test_actor_from_author(self) -> None:
        event = normalize_event(
            _raw_confluence_audit(),
            "confluence",
            "cloud",
            "audit",
        )
        assert event.actor_raw == "conf-user-1"

    def test_unknown_maps_to_summary(self) -> None:
        event = normalize_event(
            _raw_confluence_audit(summary="Custom action done"),
            "confluence",
            "cloud",
            "audit",
        )
        assert event.operation == "custom_action_done"
        assert event.severity == "medium"


class TestJsmAuditNormalization:
    def test_group_membership(self) -> None:
        event = normalize_event(
            _raw_jsm_audit(summary="User added to group"),
            "jsm",
            "cloud",
            "audit",
        )
        assert event.id == "cloud:jsm:jsm-300"
        assert event.product == "jsm"
        assert event.operation == "group_membership_changed"
        assert event.severity == "high"

    def test_permission_changed(self) -> None:
        event = normalize_event(
            _raw_jsm_audit(summary="Permission scheme updated"),
            "jsm",
            "cloud",
            "audit",
        )
        assert event.operation == "permission_changed"


class TestOrgEventNormalization:
    def test_user_added_to_org(self) -> None:
        event = normalize_event(
            _raw_org_event(action="user_added_to_org"),
            "jira",
            "cloud",
            "activity",
        )
        assert event.id == "cloud:org:org-evt-1"
        assert event.operation == "user_added_to_org"
        assert event.severity == "medium"
        assert event.category == "security"
        assert event.source_ip == "203.0.113.5"
        assert event.context == {"reason": "onboarding"}

    def test_api_key_created(self) -> None:
        event = normalize_event(
            _raw_org_event(action="api_key_created"),
            "jira",
            "cloud",
            "activity",
        )
        assert event.severity == "high"

    def test_unknown_org_action(self) -> None:
        event = normalize_event(
            _raw_org_event(action="new_unknown_action"),
            "jira",
            "cloud",
            "activity",
        )
        assert event.operation == "new_unknown_action"
        assert event.severity == "medium"


class TestBitbucketAuditGap:
    def test_bitbucket_audit_not_implemented(self) -> None:
        raw = RawEvent(
            source_id="bb-1",
            occurred_at=datetime(2026, 4, 1, tzinfo=UTC),
            event_type="test",
            payload={},
        )
        with pytest.raises(NotImplementedError):
            normalize_event(raw, "bitbucket", "cloud", "audit")
