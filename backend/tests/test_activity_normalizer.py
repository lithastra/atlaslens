from datetime import UTC, datetime

from atlaslens.connectors.base import RawEvent
from atlaslens.normalize.normalizer import normalize_event


class TestJiraActivityNormalization:
    def test_issue_created(self) -> None:
        raw = RawEvent(
            source_id="PROJ-1",
            occurred_at=datetime(2026, 4, 20, 10, 0, tzinfo=UTC),
            event_type="issue_created",
            payload={
                "key": "PROJ-1",
                "fields": {
                    "summary": "Test issue",
                    "updated": "2026-04-20",
                    "created": "2026-04-20",
                    "creator": {"accountId": "user-1"},
                    "project": {"key": "PROJ"},
                },
            },
        )
        event = normalize_event(raw, "jira", "cloud", "activity")
        assert event.id == "cloud:jira:PROJ-1"
        assert event.operation == "issue_created"
        assert event.category == "content"
        assert event.severity == "low"
        assert event.pipeline == "activity"
        assert event.object_type == "ticket"

    def test_issue_transitioned(self) -> None:
        raw = RawEvent(
            source_id="PROJ-1-cl-99",
            occurred_at=datetime(2026, 4, 20, 10, 0, tzinfo=UTC),
            event_type="issue_transitioned",
            payload={
                "issue_key": "PROJ-1",
                "changelog_id": "99",
                "author": {"accountId": "user-1"},
                "items": [],
            },
        )
        event = normalize_event(raw, "jira", "cloud", "activity")
        assert event.operation == "issue_transitioned"
        assert event.actor_raw == "user-1"


class TestConfluenceActivityNormalization:
    def test_page_edited(self) -> None:
        raw = RawEvent(
            source_id="page-123-v3",
            occurred_at=datetime(2026, 4, 20, 10, 0, tzinfo=UTC),
            event_type="page_edited",
            payload={
                "page_id": "123",
                "title": "Roadmap",
                "space_id": "ENG",
                "author_id": "u1",
                "version": {"number": 3},
            },
        )
        event = normalize_event(
            raw, "confluence", "cloud", "activity"
        )
        assert event.id == "cloud:confluence:page-123-v3"
        assert event.operation == "page_edited"
        assert event.category == "content"
        assert event.object_type == "page"
        assert event.object_ref.name == "Roadmap"

    def test_page_created(self) -> None:
        raw = RawEvent(
            source_id="page-456-v1",
            occurred_at=datetime(2026, 4, 20, 10, 0, tzinfo=UTC),
            event_type="page_created",
            payload={
                "page_id": "456",
                "title": "New",
                "space_id": "HR",
                "author_id": "u2",
                "version": {"number": 1},
            },
        )
        event = normalize_event(
            raw, "confluence", "cloud", "activity"
        )
        assert event.operation == "page_created"


class TestBitbucketActivityNormalization:
    def test_commit(self) -> None:
        raw = RawEvent(
            source_id="abc123def456",
            occurred_at=datetime(2026, 4, 20, 10, 0, tzinfo=UTC),
            event_type="commit_pushed",
            payload={
                "hash": "abc123def456",
                "message": "Fix login bug\n\nDetailed description",
                "repo": "web-frontend",
                "author": {
                    "raw": "Alice <a@x.com>",
                    "account_id": "u1",
                },
            },
        )
        event = normalize_event(
            raw, "bitbucket", "cloud", "activity"
        )
        assert event.id == "cloud:bitbucket:abc123def456"
        assert event.operation == "commit_pushed"
        assert event.category == "content"
        assert event.object_type == "repo"
        assert event.object_ref.name == "Fix login bug"
        assert event.object_ref.container == "web-frontend"
        assert event.actor_raw == "u1"

    def test_pr_merged(self) -> None:
        raw = RawEvent(
            source_id="pr-web-frontend-42",
            occurred_at=datetime(2026, 4, 20, 10, 0, tzinfo=UTC),
            event_type="pull_request_merged",
            payload={
                "id": 42,
                "title": "Add feature X",
                "repo": "web-frontend",
                "author": {"account_id": "u1"},
            },
        )
        event = normalize_event(
            raw, "bitbucket", "cloud", "activity"
        )
        assert event.operation == "pull_request_merged"
        assert event.object_ref.name == "Add feature X"


class TestJsmActivityNormalization:
    def test_request_created(self) -> None:
        raw = RawEvent(
            source_id="jsm-SD-100",
            occurred_at=datetime(2026, 4, 20, 10, 0, tzinfo=UTC),
            event_type="request_created",
            payload={
                "key": "SD-100",
                "fields": {
                    "summary": "VPN access",
                    "creator": {"accountId": "u1"},
                    "project": {"key": "SD"},
                },
            },
        )
        event = normalize_event(raw, "jsm", "cloud", "activity")
        assert event.id == "cloud:jsm:jsm-SD-100"
        assert event.operation == "request_created"
        assert event.category == "content"
        assert event.object_type == "request"
        assert event.object_ref.container == "SD"
