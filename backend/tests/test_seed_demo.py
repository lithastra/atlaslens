from atlaslens.cli.seed_demo import build_demo_dataset
from atlaslens.models.event import Event


def test_dataset_counts_and_validity() -> None:
    data = build_demo_dataset(events=500, days=60)

    assert len(data.events) == 500
    assert len(data.identities) == 12
    assert len(data.canonical_groups) == 4
    assert data.group_membership  # non-empty

    # Every event validates against the Event model.
    for doc in data.events:
        Event(**doc)


def test_both_pipelines_and_all_products_present() -> None:
    data = build_demo_dataset(events=3000, days=90)
    pipelines = {e["pipeline"] for e in data.events}
    products = {e["product"] for e in data.events}
    assert pipelines == {"audit", "activity"}
    # all four products appear (jsm only in activity is fine — it's present)
    assert {"jira", "confluence", "bitbucket", "jsm"} <= products


def test_referential_integrity() -> None:
    data = build_demo_dataset(events=1000, days=90)
    person_ids = {i["_id"] for i in data.identities}
    group_ids = {g["_id"] for g in data.canonical_groups}

    # memberships reference real people and real groups
    for m in data.group_membership:
        assert m["identity_id"] in person_ids
        assert m["canonical_group_id"] in group_ids

    # every team has at least one member (so the Group/team filter shows it)
    teams_with_members = {m["canonical_group_id"] for m in data.group_membership}
    assert teams_with_members == group_ids

    # events reference real people
    for e in data.events:
        assert e["actor_id"] in person_ids


def test_deterministic() -> None:
    a = build_demo_dataset(events=200, days=30)
    b = build_demo_dataset(events=200, days=30)
    assert [e["_id"] for e in a.events] == [e["_id"] for e in b.events]
    assert a.events[0]["operation"] == b.events[0]["operation"]


def test_security_events_have_source_ip() -> None:
    data = build_demo_dataset(events=1000, days=90)
    sec = [e for e in data.events if e["category"] == "security"]
    assert sec
    assert all(e["source_ip"] for e in sec)
