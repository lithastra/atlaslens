"""Seed AtlasLens with synthetic demo data so the dashboard can be explored
without connecting to a real Atlassian instance.

Usage:
    python -m atlaslens.cli.seed_demo                # ~4000 events, 90 days
    python -m atlaslens.cli.seed_demo --events 8000 --days 120
    python -m atlaslens.cli.seed_demo --drop         # clear demo data first

Every generated document id is prefixed with ``demo-`` (events) /
``person:demo-`` / ``canon:demo-`` so ``--drop`` can remove exactly the demo
data and nothing else.
"""

import argparse
import asyncio
import random
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, TypedDict

from atlaslens.db import close_db, connect_db


class ActivitySpec(TypedDict):
    object_type: str
    containers: list[str]
    operations: list[str]
    names: list[str]

# --- people -----------------------------------------------------------------
_NAMES = [
    "Aiko Tanaka", "Ben Carter", "Chika Mori", "Diego Alvarez",
    "Emma Schmidt", "Farid Hassan", "Grace Park", "Hiro Yamada",
    "Ines Costa", "Jamal Wright", "Keiko Sato", "Liam O'Brien",
]

# --- teams (canonical groups) -----------------------------------------------
_TEAMS = ["Engineering", "Product", "Security", "Support"]

# --- content (activity) event templates per product ------------------------
_ACTIVITY: dict[str, ActivitySpec] = {
    "jira": {
        "object_type": "ticket",
        "containers": ["ENG", "OPS", "PLATFORM"],
        "operations": ["issue_created", "issue_updated"],
        "names": [
            "Fix login redirect loop", "Add rate limiting to API",
            "Flaky pipeline on main", "Upgrade Postgres to 16",
            "Investigate memory leak", "Refactor auth middleware",
        ],
    },
    "confluence": {
        "object_type": "page",
        "containers": ["ENGDOCS", "RUNBOOKS", "PRODUCT"],
        "operations": ["page_created", "page_updated", "blogpost_created"],
        "names": [
            "Incident postmortem", "Deploy runbook", "On-call handbook",
            "Q3 roadmap", "Architecture overview", "Onboarding guide",
        ],
    },
    "bitbucket": {
        "object_type": "pull_request",
        "containers": ["core-api", "web-app", "infra"],
        "operations": ["pull_request_opened", "pull_request_merged", "commit_pushed"],
        "names": [
            "Add caching layer", "Bump dependencies", "Fix null check",
            "Wire up metrics", "Split monolith module", "Tune query plan",
        ],
    },
    "jsm": {
        "object_type": "request",
        "containers": ["SD", "ITHELP"],
        "operations": ["request_created", "request_updated"],
        "names": [
            "VPN access request", "Laptop replacement", "Password reset",
            "New hire setup", "Software license", "Permission escalation",
        ],
    },
}

# --- security (audit) event templates per product --------------------------
_AUDIT = {
    "jira": [
        ("permission_changed", "high", "project", ["ENG", "OPS"]),
        ("project_role_changed", "medium", "project", ["ENG", "PLATFORM"]),
        ("workflow_published", "low", "config", ["WORKFLOWS"]),
    ],
    "confluence": [
        ("space_permission_changed", "high", "space", ["ENGDOCS", "RUNBOOKS"]),
        ("group_membership_changed", "medium", "group", ["Engineering", "Security"]),
    ],
    "jsm": [
        ("permission_changed", "high", "project", ["SD"]),
        ("queue_configuration_changed", "low", "config", ["SD"]),
    ],
}


@dataclass
class DemoData:
    identities: list[dict[str, Any]] = field(default_factory=list)
    canonical_groups: list[dict[str, Any]] = field(default_factory=list)
    group_membership: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)


def build_demo_dataset(
    events: int = 4000,
    days: int = 90,
    seed: int = 42,
) -> DemoData:
    """Build a deterministic synthetic dataset (seeded RNG)."""
    rng = random.Random(seed)
    now = datetime.now(UTC)
    data = DemoData()

    # People + their canonical identities.
    people: list[dict[str, str]] = []
    for i, name in enumerate(_NAMES):
        pid = f"person:demo-{i:02d}"
        account = f"demo-acct-{i:02d}"
        people.append({"id": pid, "account": account, "name": name})
        data.identities.append({
            "_id": pid,
            "display_name": name,
            "emails": [],
            "accounts": [
                {"deployment": "cloud", "product": "jira", "external_id": account}
            ],
        })

    # Teams + memberships (each person in 1–2 teams; every team non-empty).
    for t, team in enumerate(_TEAMS):
        data.canonical_groups.append({
            "_id": f"canon:demo-{t}",
            "name": team,
            "description": f"{team} team (demo)",
            "source": "atlassian-org",
            "active": True,
        })
    for p_idx, person in enumerate(people):
        primary = p_idx % len(_TEAMS)
        teams = {primary}
        if rng.random() < 0.4:
            teams.add(rng.randrange(len(_TEAMS)))
        for t in teams:
            cid = f"canon:demo-{t}"
            data.group_membership.append({
                "_id": f"{cid}:{person['id']}",
                "canonical_group_id": cid,
                "identity_id": person["id"],
                "added_at": now - timedelta(days=rng.randint(30, 300)),
            })

    # Events — mix of activity (content) and audit (security), weighted so
    # recent days are busier (nicer timeseries).
    audit_share = 0.30
    for n in range(events):
        person = rng.choice(people)
        # bias toward recent: square the uniform draw
        age_days = (rng.random() ** 2) * days
        occurred = now - timedelta(
            days=age_days, minutes=rng.randint(0, 1439)
        )
        ip = f"203.0.113.{rng.randint(1, 254)}"

        if rng.random() < audit_share:
            product = rng.choice(list(_AUDIT.keys()))
            op, severity, otype, containers = rng.choice(_AUDIT[product])
            container = rng.choice(containers)
            doc = _event(
                n, product, "audit", "security", op, severity, otype,
                obj_id=f"{container}-{rng.randint(1, 99)}",
                obj_name=f"{op.replace('_', ' ')} on {container}",
                container=container, occurred=occurred, person=person, ip=ip,
            )
        else:
            product = rng.choice(list(_ACTIVITY.keys()))
            spec = _ACTIVITY[product]
            op = rng.choice(spec["operations"])
            container = rng.choice(spec["containers"])
            num = rng.randint(1, 999)
            key = f"{container}-{num}" if product in ("jira", "jsm") else f"#{num}"
            doc = _event(
                n, product, "activity", "content", op, "low",
                spec["object_type"],
                obj_id=key,
                obj_name=f"{key}: {rng.choice(spec['names'])}",
                container=container, occurred=occurred, person=person, ip=ip,
            )
        data.events.append(doc)

    return data


def _event(
    n: int,
    product: str,
    pipeline: str,
    category: str,
    operation: str,
    severity: str,
    object_type: str,
    *,
    obj_id: str,
    obj_name: str,
    container: str,
    occurred: datetime,
    person: dict[str, str],
    ip: str,
) -> dict[str, Any]:
    return {
        "_id": f"cloud:{product}:demo-{n:06d}",
        "occurred_at": occurred,
        "product": product,
        "deployment": "cloud",
        "pipeline": pipeline,
        "actor_id": person["id"],
        "actor_raw": person["account"],
        "operation": operation,
        "category": category,
        "severity": severity,
        "object_type": object_type,
        "object_ref": {"id": obj_id, "name": obj_name, "container": container},
        "context": {},
        "source_ip": ip if category == "security" else None,
        "raw": {"demo": True},
        "ingested_at": datetime.now(UTC),
    }


async def _write(db: Any, data: DemoData, drop: bool) -> None:
    if drop:
        await db["events"].delete_many({"_id": {"$regex": ":demo-"}})
        await db["identities"].delete_many({"_id": {"$regex": "^person:demo-"}})
        await db["canonical_groups"].delete_many({"_id": {"$regex": "^canon:demo-"}})
        await db["group_membership"].delete_many(
            {"_id": {"$regex": "^canon:demo-"}}
        )

    for ident in data.identities:
        await db["identities"].replace_one({"_id": ident["_id"]}, ident, upsert=True)
    for grp in data.canonical_groups:
        await db["canonical_groups"].replace_one({"_id": grp["_id"]}, grp, upsert=True)
    for mem in data.group_membership:
        await db["group_membership"].replace_one({"_id": mem["_id"]}, mem, upsert=True)

    # Events in batches for speed.
    batch: list[dict[str, Any]] = []
    for ev in data.events:
        batch.append(ev)
        if len(batch) >= 1000:
            await db["events"].insert_many(batch, ordered=False)
            batch = []
    if batch:
        await db["events"].insert_many(batch, ordered=False)


async def _seed(events: int, days: int, drop: bool) -> None:
    data = build_demo_dataset(events=events, days=days)
    db = await connect_db()
    try:
        await _write(db, data, drop)
        print(
            f"Seeded {len(data.events)} events, {len(data.identities)} people, "
            f"{len(data.canonical_groups)} teams, "
            f"{len(data.group_membership)} memberships."
        )
    finally:
        await close_db()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed synthetic demo data")
    parser.add_argument("--events", type=int, default=4000)
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Remove existing demo data before seeding",
    )
    args = parser.parse_args()
    asyncio.run(_seed(args.events, args.days, args.drop))


if __name__ == "__main__":
    main()
