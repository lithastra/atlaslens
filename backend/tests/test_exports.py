import csv
import hashlib
import io
import re
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from atlaslens.api.auth import create_access_token, hash_password
from atlaslens.api.deps import get_database
from atlaslens.api.main import app
from atlaslens.cli.verify_export import verify


class _AsyncIter:
    def __init__(self, items: list[dict[str, Any]]) -> None:
        self._items = items
        self._idx = 0

    def sort(self, *a: Any, **kw: Any) -> "_AsyncIter":
        return self

    def __aiter__(self) -> "_AsyncIter":
        self._idx = 0
        return self

    async def __anext__(self) -> dict[str, Any]:
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        return item


class _MockDB:
    def __init__(self) -> None:
        self._cols: dict[str, AsyncMock] = defaultdict(AsyncMock)

    def __getitem__(self, name: str) -> AsyncMock:
        return self._cols[name]


def _setup(db: _MockDB) -> None:
    db["users"].find_one = AsyncMock(
        return_value={
            "_id": "admin",
            "username": "admin",
            "password_hash": hash_password("secret123"),
            "created_at": datetime.now(UTC),
            "disabled": False,
        }
    )


def _auth() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_access_token('admin')}"
    }


_EVENTS = [
    {
        "_id": f"cloud:jira:evt-{i}",
        "occurred_at": datetime(2026, 4, 20, 10, i, tzinfo=UTC),
        "product": "jira",
        "deployment": "cloud",
        "pipeline": "audit",
        "actor_id": "person:001",
        "actor_raw": "u1",
        "operation": "permission_changed",
        "category": "security",
        "severity": "high",
        "object_type": "config",
        "object_ref": {"id": "x", "name": f"obj-{i}"},
        "source_ip": "10.0.0.1",
    }
    for i in range(5)
]


class TestExportEndpoint:
    def test_csv_has_header_and_rows(self) -> None:
        db = _MockDB()
        _setup(db)
        db["events"].find = lambda *a, **kw: _AsyncIter(_EVENTS)

        app.dependency_overrides[get_database] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/exports", headers=_auth())
        app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert "text/csv" in resp.headers["content-type"]

        content = resp.text
        reader = csv.DictReader(
            content.split("\n# Integrity:")[0].splitlines()
        )
        rows = list(reader)
        assert len(rows) == 5
        assert rows[0]["id"] == "cloud:jira:evt-0"

    def test_integrity_stamp_present(self) -> None:
        db = _MockDB()
        _setup(db)
        db["events"].find = lambda *a, **kw: _AsyncIter(_EVENTS)

        app.dependency_overrides[get_database] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/exports", headers=_auth())
        app.dependency_overrides.clear()

        content = resp.text
        match = re.search(
            r"# Integrity: count=(\d+) sha256=([0-9a-f]+)",
            content,
        )
        assert match is not None
        assert int(match.group(1)) == 5

    def test_integrity_stamp_verifiable(self) -> None:
        db = _MockDB()
        _setup(db)
        db["events"].find = lambda *a, **kw: _AsyncIter(_EVENTS)

        app.dependency_overrides[get_database] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/exports", headers=_auth())
        app.dependency_overrides.clear()

        content = resp.text

        stamp = re.search(
            r"# Integrity: count=(\d+) sha256=([0-9a-f]+)",
            content,
        )
        assert stamp is not None
        expected_count = int(stamp.group(1))
        expected_hash = stamp.group(2)

        body = content.split("\n# Integrity:")[0]
        reader = csv.DictReader(body.splitlines())
        hasher = hashlib.sha256()
        count = 0
        for row in reader:
            hasher.update(row["id"].encode())
            count += 1

        assert count == expected_count
        assert hasher.hexdigest() == expected_hash

    def test_empty_export(self) -> None:
        db = _MockDB()
        _setup(db)
        db["events"].find = lambda *a, **kw: _AsyncIter([])

        app.dependency_overrides[get_database] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/exports", headers=_auth())
        app.dependency_overrides.clear()

        content = resp.text
        match = re.search(r"count=(\d+)", content)
        assert match is not None
        assert int(match.group(1)) == 0


    def test_pdf_export(self) -> None:
        db = _MockDB()
        _setup(db)
        db["events"].find = lambda *a, **kw: _AsyncIter(_EVENTS)

        app.dependency_overrides[get_database] = lambda: db
        client = TestClient(app, raise_server_exceptions=False)
        resp = client.post("/exports?format=pdf", headers=_auth())
        app.dependency_overrides.clear()

        assert resp.status_code == 200
        assert "application/pdf" in resp.headers["content-type"]
        assert resp.content[:5] == b"%PDF-"
        assert len(resp.content) > 500


class TestVerifyCli:
    def test_verify_valid_file(self, tmp_path: Any) -> None:
        buf = io.StringIO()
        fields = [
            "id",
            "occurred_at",
            "product",
            "deployment",
            "pipeline",
            "actor_id",
            "actor_raw",
            "operation",
            "category",
            "severity",
            "object_type",
            "object_ref_id",
            "object_ref_name",
            "object_ref_container",
            "source_ip",
        ]
        writer = csv.DictWriter(buf, fieldnames=fields)
        writer.writeheader()

        hasher = hashlib.sha256()
        for i in range(3):
            event_id = f"cloud:jira:evt-{i}"
            writer.writerow({f: event_id if f == "id" else "" for f in fields})
            hasher.update(event_id.encode())

        buf.write(
            f"\n# Integrity: count=3 "
            f"sha256={hasher.hexdigest()} "
            f"generated_at=2026-05-26T00:00:00"
        )

        path = tmp_path / "export.csv"
        path.write_text(buf.getvalue())
        assert verify(str(path)) is True

    def test_verify_tampered_file(self, tmp_path: Any) -> None:
        buf = io.StringIO()
        fields = ["id", "occurred_at"]
        writer = csv.DictWriter(buf, fieldnames=fields)
        writer.writeheader()
        writer.writerow({"id": "evt-1", "occurred_at": ""})
        buf.write(
            "\n# Integrity: count=1 "
            "sha256=0000000000000000000000000000000000000000000000000000000000000000 "
            "generated_at=2026-05-26T00:00:00"
        )

        path = tmp_path / "tampered.csv"
        path.write_text(buf.getvalue())
        assert verify(str(path)) is False
