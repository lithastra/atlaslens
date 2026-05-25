from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from atlaslens.models.event import Event, ObjectRef
from atlaslens.models.group import CanonicalGroup, GroupMap, SourceGroup
from atlaslens.models.identity import AccountLink, Identity
from atlaslens.models.sync_state import SyncState
from atlaslens.models.user import User


class TestEvent:
    def test_valid_event(self) -> None:
        event = Event(
            _id="cloud:jira:evt-001",
            occurred_at=datetime.now(UTC),
            product="jira",
            deployment="cloud",
            pipeline="audit",
            actor_raw="abc123",
            operation="permission_changed",
            category="security",
            severity="high",
            object_type="space",
            object_ref=ObjectRef(id="ENG", name="Engineering"),
        )
        assert event.id == "cloud:jira:evt-001"
        assert event.product == "jira"
        assert event.pipeline == "audit"

    def test_to_doc_uses_alias(self) -> None:
        event = Event(
            _id="cloud:jira:evt-002",
            occurred_at=datetime.now(UTC),
            product="jira",
            deployment="cloud",
            pipeline="activity",
            actor_raw="abc123",
            operation="issue_created",
            category="content",
            severity="low",
            object_type="ticket",
            object_ref=ObjectRef(id="PROJ-1", name="Test ticket"),
        )
        doc = event.to_doc()
        assert "_id" in doc
        assert "id" not in doc

    def test_rejects_invalid_product(self) -> None:
        with pytest.raises(ValidationError):
            Event(
                _id="test",
                occurred_at=datetime.now(UTC),
                product="invalid",  # type: ignore[arg-type]
                deployment="cloud",
                pipeline="audit",
                actor_raw="x",
                operation="op",
                category="security",
                severity="low",
                object_type="ticket",
                object_ref=ObjectRef(id="1", name="x"),
            )

    def test_rejects_invalid_severity(self) -> None:
        with pytest.raises(ValidationError):
            Event(
                _id="test",
                occurred_at=datetime.now(UTC),
                product="jira",
                deployment="cloud",
                pipeline="audit",
                actor_raw="x",
                operation="op",
                category="security",
                severity="critical",  # type: ignore[arg-type]
                object_type="ticket",
                object_ref=ObjectRef(id="1", name="x"),
            )

    def test_optional_fields_default(self) -> None:
        event = Event(
            _id="cloud:confluence:evt-003",
            occurred_at=datetime.now(UTC),
            product="confluence",
            deployment="cloud",
            pipeline="activity",
            actor_raw="user456",
            operation="page_created",
            category="content",
            severity="low",
            object_type="page",
            object_ref=ObjectRef(id="12345", name="Roadmap"),
        )
        assert event.actor_id is None
        assert event.source_ip is None
        assert event.context == {}
        assert event.raw == {}


class TestUser:
    def test_valid_user(self) -> None:
        user = User(
            username="admin",
            password_hash="$2b$12$hash",
        )
        assert user.username == "admin"
        assert user.disabled is False


class TestIdentity:
    def test_identity_with_accounts(self) -> None:
        identity = Identity(
            _id="person:0042",
            display_name="Alice Chen",
            emails=["alice@example.com"],
            accounts=[
                AccountLink(
                    deployment="cloud", product="jira", external_id="5f8a"
                )
            ],
        )
        assert identity.id == "person:0042"
        assert len(identity.accounts) == 1


class TestSyncState:
    def test_sync_state(self) -> None:
        state = SyncState(_id="cloud:jira:audit", cursor="2026-01-01T00:00:00Z")
        assert state.id == "cloud:jira:audit"
        assert state.last_error is None


class TestGroups:
    def test_canonical_group(self) -> None:
        group = CanonicalGroup(_id="grp-001", name="Engineering")
        assert group.source == "atlassian-org"
        assert group.active is True

    def test_source_group(self) -> None:
        sg = SourceGroup(
            _id="sg-001",
            namespace="atlassian-org",
            native_id="abc123",
            native_name="Engineering",
        )
        assert sg.namespace == "atlassian-org"

    def test_group_map(self) -> None:
        gm = GroupMap(
            _id="gm-001",
            source_group_id="sg-001",
            canonical_group_id="grp-001",
        )
        assert gm.match_method == "auto_name"
        assert gm.confidence == 1.0
