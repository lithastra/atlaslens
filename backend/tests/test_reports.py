from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import pytest

from atlaslens.reports.generator import generate_report, run_scheduled_reports
from tests.mock_db import MockDB


def _make_events(n: int) -> list[dict[str, Any]]:
    return [
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
        for i in range(n)
    ]


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


class TestGenerateReport:
    @pytest.mark.asyncio
    async def test_csv_report(self, tmp_path: Any) -> None:
        import atlaslens.reports.generator as gen

        orig = gen.settings.report_output_dir
        gen.settings.report_output_dir = str(tmp_path)

        db = MockDB()
        db["events"].find = lambda *a, **kw: _AsyncIter(_make_events(3))
        db["scheduled_reports"].update_one = AsyncMock()

        report_def: dict[str, Any] = {
            "_id": "report:test1",
            "name": "test report",
            "format": "csv",
            "filters": {},
        }
        path = await generate_report(db, report_def)  # type: ignore[arg-type]

        gen.settings.report_output_dir = orig

        assert path.endswith(".csv")
        with open(path) as f:
            content = f.read()
        assert "cloud:jira:evt-0" in content
        assert "# Integrity:" in content

    @pytest.mark.asyncio
    async def test_pdf_report(self, tmp_path: Any) -> None:
        import atlaslens.reports.generator as gen

        orig = gen.settings.report_output_dir
        gen.settings.report_output_dir = str(tmp_path)

        db = MockDB()
        db["events"].find = lambda *a, **kw: _AsyncIter(_make_events(2))
        db["scheduled_reports"].update_one = AsyncMock()

        report_def: dict[str, Any] = {
            "_id": "report:test2",
            "name": "pdf test",
            "format": "pdf",
            "filters": {},
        }
        path = await generate_report(db, report_def)  # type: ignore[arg-type]

        gen.settings.report_output_dir = orig

        assert path.endswith(".pdf")
        with open(path, "rb") as f:
            assert f.read(5) == b"%PDF-"


class TestRunScheduledReports:
    @pytest.mark.asyncio
    async def test_skips_recently_run(self) -> None:
        db = MockDB()
        db["scheduled_reports"].find = lambda *a, **kw: _AsyncIter([
            {
                "_id": "report:recent",
                "name": "recent",
                "schedule": "monthly",
                "format": "csv",
                "filters": {},
                "enabled": True,
                "last_run_at": datetime.now(UTC),
            }
        ])

        count = await run_scheduled_reports(db)  # type: ignore[arg-type]
        assert count == 0

    @pytest.mark.asyncio
    async def test_runs_due_report(self, tmp_path: Any) -> None:
        import atlaslens.reports.generator as gen

        orig = gen.settings.report_output_dir
        gen.settings.report_output_dir = str(tmp_path)

        db = MockDB()
        db["events"].find = lambda *a, **kw: _AsyncIter(_make_events(1))
        db["scheduled_reports"].update_one = AsyncMock()
        db["scheduled_reports"].find = lambda *a, **kw: _AsyncIter([
            {
                "_id": "report:due",
                "name": "overdue",
                "schedule": "monthly",
                "format": "csv",
                "filters": {},
                "enabled": True,
                "last_run_at": datetime(2026, 1, 1, tzinfo=UTC),
            }
        ])

        count = await run_scheduled_reports(db)  # type: ignore[arg-type]

        gen.settings.report_output_dir = orig

        assert count == 1
