from datetime import UTC, datetime

import pytest

from atlaslens.connectors.base import RawEvent
from atlaslens.normalize.normalizer import normalize_event


def _raw_jira_audit(
    source_id: str = "100",
    summary: str = "User added to group",
    category: str = "group management",
    type_name: str = "GROUP",
    object_name: str = "jira-administrators",
    actor: str = "5f8abc",
    ip: str = "192.168.1.1",
    changed_values: list | None = None,
) -> RawEvent:
    return RawEvent(
        source_id=source_id,
        occurred_at=datetime(2026, 3, 15, 10, 0, tzinfo=UTC),
        event_type=summary,
        payload={
            "id": int(source_id),
            "summary": summary,
            "remoteAddress": ip,
            "authorAccountId": actor,
            "created": "2026-03-15T10:00:00.000+0000",
            "category": category,
            "eventSource": "Jira",
            "objectItem": {
                "id": "obj-1",
                "name": object_name,
                "typeName": type_name,
                "parentName": None,
            },
            "changedValues": changed_values or [],
            "associatedItems": [],
        },
    )


class TestJiraAuditNormalization:
    def test_group_membership_change(self) -> None:
        event = normalize_event(
            _raw_jira_audit(summary="User added to group"),
            product="jira",
            deployment="cloud",
            pipeline="audit",
        )
        assert event.id == "cloud:jira:100"
        assert event.operation == "group_membership_changed"
        assert event.severity == "high"
        assert event.category == "security"
        assert event.pipeline == "audit"
        assert event.object_type == "group"

    def test_permission_changed(self) -> None:
        event = normalize_event(
            _raw_jira_audit(
                summary="Permission scheme updated",
                type_name="PERMISSION_SCHEME",
                object_name="Default Permission Scheme",
            ),
            product="jira",
            deployment="cloud",
            pipeline="audit",
        )
        assert event.operation == "permission_changed"
        assert event.severity == "high"
        assert event.object_type == "config"

    def test_user_created(self) -> None:
        event = normalize_event(
            _raw_jira_audit(
                summary="User created",
                category="user management",
                type_name="USER",
                object_name="alice",
            ),
            product="jira",
            deployment="cloud",
            pipeline="audit",
        )
        assert event.operation == "user_created"
        assert event.severity == "medium"
        assert event.object_type == "user"

    def test_project_deleted(self) -> None:
        event = normalize_event(
            _raw_jira_audit(
                summary="Project deleted",
                type_name="PROJECT",
                object_name="OLD",
            ),
            product="jira",
            deployment="cloud",
            pipeline="audit",
        )
        assert event.operation == "project_deleted"
        assert event.severity == "high"
        assert event.object_type == "project"

    def test_global_config_changed(self) -> None:
        event = normalize_event(
            _raw_jira_audit(summary="Global permission changed"),
            product="jira",
            deployment="cloud",
            pipeline="audit",
        )
        assert event.operation == "permission_changed"
        assert event.severity == "high"

    def test_unknown_operation_uses_summary(self) -> None:
        event = normalize_event(
            _raw_jira_audit(summary="Something unexpected happened"),
            product="jira",
            deployment="cloud",
            pipeline="audit",
        )
        assert event.operation == "something_unexpected_happened"
        assert event.severity == "medium"

    def test_actor_from_account_id(self) -> None:
        event = normalize_event(
            _raw_jira_audit(actor="account-xyz"),
            product="jira",
            deployment="cloud",
            pipeline="audit",
        )
        assert event.actor_raw == "account-xyz"

    def test_source_ip_captured(self) -> None:
        event = normalize_event(
            _raw_jira_audit(ip="203.0.113.7"),
            product="jira",
            deployment="cloud",
            pipeline="audit",
        )
        assert event.source_ip == "203.0.113.7"

    def test_changed_values_in_context(self) -> None:
        event = normalize_event(
            _raw_jira_audit(
                summary="Permission scheme updated",
                changed_values=[
                    {"fieldName": "role", "changedFrom": "read", "changedTo": "admin"}
                ],
            ),
            product="jira",
            deployment="cloud",
            pipeline="audit",
        )
        assert event.context["role"] == {"from": "read", "to": "admin"}

    def test_raw_payload_preserved(self) -> None:
        raw = _raw_jira_audit()
        event = normalize_event(raw, "jira", "cloud", "audit")
        assert event.raw == raw.payload

    def test_natural_id_format(self) -> None:
        event = normalize_event(
            _raw_jira_audit(source_id="42"),
            product="jira",
            deployment="cloud",
            pipeline="audit",
        )
        assert event.id == "cloud:jira:42"

    def test_datacenter_deployment(self) -> None:
        event = normalize_event(
            _raw_jira_audit(),
            product="jira",
            deployment="datacenter",
            pipeline="audit",
        )
        assert event.id == "datacenter:jira:100"
        assert event.deployment == "datacenter"

    def test_unimplemented_product_raises(self) -> None:
        with pytest.raises(NotImplementedError):
            normalize_event(
                _raw_jira_audit(),
                product="confluence",
                deployment="cloud",
                pipeline="audit",
            )

    def test_unknown_object_type_defaults_to_config(self) -> None:
        event = normalize_event(
            _raw_jira_audit(type_name="SOMETHING_NEW"),
            product="jira",
            deployment="cloud",
            pipeline="audit",
        )
        assert event.object_type == "config"
