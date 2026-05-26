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


_CONFLUENCE_AUDIT_OPERATIONS: list[tuple[str, str, Severity]] = [
    ("permission", "permission_changed", "high"),
    ("added to group", "group_membership_changed", "high"),
    ("removed from group", "group_membership_changed", "high"),
    ("space export", "data_exported", "high"),
    ("space created", "space_created", "low"),
    ("space deleted", "space_deleted", "high"),
    ("space updated", "space_updated", "low"),
    ("user created", "user_created", "medium"),
    ("user deactivated", "user_deactivated", "medium"),
    ("global", "global_config_changed", "high"),
    ("application", "app_changed", "medium"),
]

_ORG_EVENT_SEVERITY: dict[str, Severity] = {
    "user_added_to_org": "medium",
    "user_removed_from_org": "medium",
    "user_deactivated": "medium",
    "user_reactivated": "medium",
    "org_policy_changed": "high",
    "api_key_created": "high",
    "api_key_revoked": "high",
    "domain_verified": "medium",
    "domain_removed": "high",
    "product_access_changed": "high",
    "managed_account_updated": "medium",
}


def normalize_event(
    raw: RawEvent,
    product: Product,
    deployment: Deployment,
    pipeline: Pipeline,
) -> Event:
    if pipeline == "audit":
        if product == "jira":
            return _normalize_jira_audit(raw, deployment)
        if product == "confluence":
            return _normalize_confluence_audit(raw, deployment)
        if product == "jsm":
            return _normalize_jsm_audit(raw, deployment)
    if pipeline == "activity":
        if product == "jira":
            if raw.event_type in _ORG_EVENT_SEVERITY or (
                raw.payload.get("attributes") is not None
            ):
                return _normalize_org_event(raw, deployment)
            return _normalize_jira_activity(raw, deployment)
        if product == "confluence":
            return _normalize_confluence_activity(raw, deployment)
        if product == "bitbucket":
            return _normalize_bitbucket_activity(raw, deployment)
        if product == "jsm":
            return _normalize_jsm_activity(raw, deployment)
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
        id=f"{deployment}:jira:{raw.source_id}",
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
            ctx[field] = {
                "from": cv.get("changedFrom"),
                "to": cv.get("changedTo"),
            }
    return ctx


def _normalize_confluence_audit(
    raw: RawEvent, deployment: Deployment
) -> Event:
    p: dict[str, Any] = raw.payload
    summary = p.get("summary", "").lower()

    operation, severity = _classify_confluence_operation(summary)

    obj: dict[str, Any] = p.get("objectItem") or {}
    type_name = (obj.get("typeName") or "").upper()
    object_type: ObjectType = _OBJECT_TYPE_MAP.get(type_name, "config")
    if object_type == "config" and "space" in type_name.lower():
        object_type = "space"

    author: dict[str, Any] = p.get("author", {})
    actor_raw = author.get("accountId", author.get("username", ""))

    return Event(
        id=f"{deployment}:confluence:{raw.source_id}",
        occurred_at=raw.occurred_at,
        product="confluence",
        deployment=deployment,
        pipeline="audit",
        actor_raw=actor_raw,
        operation=operation,
        category="security",
        severity=severity,
        object_type=object_type,
        object_ref=ObjectRef(
            id=obj.get("id", ""),
            name=obj.get("name", ""),
            container=obj.get("parentName"),
        ),
        context=_extract_changed_values(p),
        source_ip=p.get("remoteAddress"),
        raw=p,
    )


def _classify_confluence_operation(
    summary: str,
) -> tuple[str, Severity]:
    for keyword, operation, severity in _CONFLUENCE_AUDIT_OPERATIONS:
        if keyword in summary:
            return operation, severity
    return summary.replace(" ", "_"), "medium"


def _normalize_jsm_audit(
    raw: RawEvent, deployment: Deployment
) -> Event:
    p: dict[str, Any] = raw.payload
    summary = p.get("summary", "").lower()
    operation, severity = _classify_jira_operation(summary)

    object_item: dict[str, Any] = p.get("objectItem") or {}
    type_name = (object_item.get("typeName") or "").upper()
    object_type: ObjectType = _OBJECT_TYPE_MAP.get(type_name, "config")

    return Event(
        id=f"{deployment}:jsm:{raw.source_id}",
        occurred_at=raw.occurred_at,
        product="jsm",
        deployment=deployment,
        pipeline="audit",
        actor_raw=p.get(
            "authorAccountId", p.get("authorKey", "")
        ),
        operation=operation,
        category="security",
        severity=severity,
        object_type=object_type,
        object_ref=ObjectRef(
            id=object_item.get("id", ""),
            name=object_item.get("name", ""),
            container=object_item.get("parentName"),
        ),
        context=_extract_changed_values(p),
        source_ip=p.get("remoteAddress"),
        raw=p,
    )


def _normalize_org_event(
    raw: RawEvent, deployment: Deployment
) -> Event:
    p: dict[str, Any] = raw.payload
    attrs: dict[str, Any] = p.get("attributes", {})
    action = attrs.get("action", raw.event_type)
    severity = _ORG_EVENT_SEVERITY.get(action, "medium")

    actor_data: dict[str, Any] = attrs.get("actor", {})
    actor_raw = actor_data.get("id", "")

    target: dict[str, Any] = attrs.get("target", {})

    return Event(
        id=f"{deployment}:org:{raw.source_id}",
        occurred_at=raw.occurred_at,
        product="jira",
        deployment=deployment,
        pipeline="audit",
        actor_raw=actor_raw,
        operation=action,
        category="security",
        severity=severity,
        object_type="config",
        object_ref=ObjectRef(
            id=target.get("id", ""),
            name=target.get("name", action),
        ),
        context=attrs.get("context", {}),
        source_ip=attrs.get("location", {}).get("ip"),
        raw=p,
    )


def _normalize_jira_activity(
    raw: RawEvent, deployment: Deployment
) -> Event:
    p: dict[str, Any] = raw.payload
    fields: dict[str, Any] = p.get("fields", {})
    creator = fields.get("creator") or {}
    project = fields.get("project") or {}

    operation = raw.event_type
    if operation not in (
        "issue_created",
        "issue_updated",
        "issue_transitioned",
        "comment_added",
    ):
        operation = "issue_updated"

    actor_raw = ""
    if "author" in p and isinstance(p["author"], dict):
        actor_raw = p["author"].get("accountId", "")
    if not actor_raw:
        actor_raw = creator.get("accountId", "")

    return Event(
        id=f"{deployment}:jira:{raw.source_id}",
        occurred_at=raw.occurred_at,
        product="jira",
        deployment=deployment,
        pipeline="activity",
        actor_raw=actor_raw,
        operation=operation,
        category="content",
        severity="low",
        object_type="ticket",
        object_ref=ObjectRef(
            id=p.get("key", raw.source_id),
            name=fields.get("summary", ""),
            container=project.get("key"),
        ),
        raw=p,
    )


def _normalize_confluence_activity(
    raw: RawEvent, deployment: Deployment
) -> Event:
    p: dict[str, Any] = raw.payload

    return Event(
        id=f"{deployment}:confluence:{raw.source_id}",
        occurred_at=raw.occurred_at,
        product="confluence",
        deployment=deployment,
        pipeline="activity",
        actor_raw=p.get("author_id", ""),
        operation=raw.event_type,
        category="content",
        severity="low",
        object_type="page",
        object_ref=ObjectRef(
            id=p.get("page_id", ""),
            name=p.get("title", ""),
            container=p.get("space_id"),
        ),
        raw=p,
    )


def _normalize_bitbucket_activity(
    raw: RawEvent, deployment: Deployment
) -> Event:
    p: dict[str, Any] = raw.payload
    author: dict[str, Any] = p.get("author", {})
    actor_raw = author.get("account_id", author.get("raw", ""))

    obj_name = ""
    if raw.event_type == "commit_pushed":
        msg = p.get("message", "")
        obj_name = msg.split("\n", 1)[0][:120] if msg else ""
    else:
        obj_name = p.get("title", "")

    return Event(
        id=f"{deployment}:bitbucket:{raw.source_id}",
        occurred_at=raw.occurred_at,
        product="bitbucket",
        deployment=deployment,
        pipeline="activity",
        actor_raw=actor_raw,
        operation=raw.event_type,
        category="content",
        severity="low",
        object_type="repo",
        object_ref=ObjectRef(
            id=str(p.get("hash", p.get("id", raw.source_id))),
            name=obj_name,
            container=p.get("repo"),
        ),
        raw=p,
    )


def _normalize_jsm_activity(
    raw: RawEvent, deployment: Deployment
) -> Event:
    p: dict[str, Any] = raw.payload
    fields: dict[str, Any] = p.get("fields", {})
    creator = fields.get("creator") or {}
    project = fields.get("project") or {}

    return Event(
        id=f"{deployment}:jsm:{raw.source_id}",
        occurred_at=raw.occurred_at,
        product="jsm",
        deployment=deployment,
        pipeline="activity",
        actor_raw=creator.get("accountId", ""),
        operation=raw.event_type,
        category="content",
        severity="low",
        object_type="request",
        object_ref=ObjectRef(
            id=p.get("key", raw.source_id),
            name=fields.get("summary", ""),
            container=project.get("key"),
        ),
        raw=p,
    )
