from typing import Any

from atlaslens.connectors.base import RawEvent
from atlaslens.models.event import (
    Deployment,
    Event,
    ObjectRef,
    ObjectType,
    Pipeline,
    Product,
    Severity,
)

_JIRA_AUDIT_OPERATIONS: list[tuple[str, str, Severity]] = [
    ("added to group", "group_membership_changed", "high"),
    ("removed from group", "group_membership_changed", "high"),
    ("group membership", "group_membership_changed", "high"),
    ("group created", "group_created", "medium"),
    ("group deleted", "group_deleted", "high"),
    ("permission", "permission_changed", "high"),
    ("user created", "user_created", "medium"),
    ("user deleted", "user_deactivated", "medium"),
    ("user deactivated", "user_deactivated", "medium"),
    ("user reactivated", "user_reactivated", "medium"),
    ("project created", "project_created", "low"),
    ("project deleted", "project_deleted", "high"),
    ("project updated", "project_updated", "low"),
    ("scheme", "scheme_changed", "medium"),
    ("workflow", "workflow_changed", "low"),
    ("filter", "filter_changed", "low"),
    ("global", "global_config_changed", "high"),
    ("application", "app_changed", "medium"),
    ("export", "data_exported", "high"),
]

_OBJECT_TYPE_MAP: dict[str, ObjectType] = {
    "GROUP": "group",
    "USER": "user",
    "PROJECT": "project",
    "PROJECT_ROLE": "project",
    "SCHEME": "config",
    "PERMISSION_SCHEME": "config",
    "NOTIFICATION_SCHEME": "config",
    "WORKFLOW": "config",
    "WORKFLOW_SCHEME": "config",
    "FILTER": "config",
    "CUSTOM_FIELD": "config",
    "DASHBOARD": "config",
    "SCREEN": "config",
    "ISSUE": "ticket",
    "SPACE": "space",
}


def normalize_event(
    raw: RawEvent,
    product: Product,
    deployment: Deployment,
    pipeline: Pipeline,
) -> Event:
    if product == "jira" and pipeline == "audit":
        return _normalize_jira_audit(raw, deployment)
    raise NotImplementedError(
        f"normalizer for {product}/{pipeline} not yet implemented"
    )


def _normalize_jira_audit(raw: RawEvent, deployment: Deployment) -> Event:
    p: dict[str, Any] = raw.payload
    summary = p.get("summary", "").lower()

    operation, severity = _classify_jira_operation(summary)

    object_item: dict[str, Any] = p.get("objectItem") or {}
    type_name = (object_item.get("typeName") or "").upper()
    object_type: ObjectType = _OBJECT_TYPE_MAP.get(type_name, "config")

    context = _extract_changed_values(p)

    return Event(
        _id=f"{deployment}:jira:{raw.source_id}",
        occurred_at=raw.occurred_at,
        product="jira",
        deployment=deployment,
        pipeline="audit",
        actor_raw=p.get("authorAccountId", p.get("authorKey", "")),
        operation=operation,
        category="security",
        severity=severity,
        object_type=object_type,
        object_ref=ObjectRef(
            id=object_item.get("id", ""),
            name=object_item.get("name", ""),
            container=object_item.get("parentName"),
        ),
        context=context,
        source_ip=p.get("remoteAddress"),
        raw=p,
    )


def _classify_jira_operation(summary: str) -> tuple[str, Severity]:
    for keyword, operation, severity in _JIRA_AUDIT_OPERATIONS:
        if keyword in summary:
            return operation, severity
    return summary.replace(" ", "_"), "medium"


def _extract_changed_values(payload: dict[str, Any]) -> dict[str, Any]:
    changed: list[dict[str, Any]] = payload.get("changedValues", [])
    if not changed:
        return {}
    ctx: dict[str, Any] = {}
    for cv in changed:
        field = cv.get("fieldName", "")
        if field:
            ctx[field] = {"from": cv.get("changedFrom"), "to": cv.get("changedTo")}
    return ctx
