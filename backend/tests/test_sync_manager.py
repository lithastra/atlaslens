import asyncio
from typing import Any

import pytest

from atlaslens.ingest import manager as mgr_mod
from atlaslens.ingest import scheduler

# The manager never touches the db itself (it forwards to run_all, which we
# stub), so a typed-None placeholder is sufficient for these tests.
_DB: Any = None


@pytest.mark.asyncio
async def test_run_completes_and_records_progress(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    m = mgr_mod.SyncManager()

    async def fake_run_all(db: Any, report: Any = None) -> dict[str, Any]:
        report("cloud:jira:audit", "done", count=5)
        return {"jira:audit": 5}

    monkeypatch.setattr(scheduler, "run_all", fake_run_all)

    assert await m.start(_DB, cancel_existing=False) == "started"
    assert m._task is not None
    await m._task

    assert m.running is False
    assert m.connectors["cloud:jira:audit"]["state"] == "done"
    assert m.connectors["cloud:jira:audit"]["count"] == 5
    snap = m.snapshot()
    assert snap["running"] is False
    assert snap["connectors"]["cloud:jira:audit"]["state"] == "done"


@pytest.mark.asyncio
async def test_second_start_is_busy_without_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    m = mgr_mod.SyncManager()
    started = asyncio.Event()
    release = asyncio.Event()

    async def fake_run_all(db: Any, report: Any = None) -> dict[str, Any]:
        started.set()
        await release.wait()
        return {}

    monkeypatch.setattr(scheduler, "run_all", fake_run_all)

    assert await m.start(_DB, cancel_existing=False) == "started"
    await started.wait()
    assert await m.start(_DB, cancel_existing=False) == "busy"

    release.set()
    assert m._task is not None
    await m._task
    assert m.running is False


@pytest.mark.asyncio
async def test_cancel_marks_running_connectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    m = mgr_mod.SyncManager()
    started = asyncio.Event()

    async def fake_run_all(db: Any, report: Any = None) -> dict[str, Any]:
        report("cloud:jira:audit", "running")
        started.set()
        await asyncio.sleep(3600)  # block until cancelled
        return {}

    monkeypatch.setattr(scheduler, "run_all", fake_run_all)

    await m.start(_DB, cancel_existing=False)
    await started.wait()
    await m.cancel()

    assert m.running is False
    assert m.cancelled is True
    assert m.connectors["cloud:jira:audit"]["state"] == "cancelled"


@pytest.mark.asyncio
async def test_cancel_existing_replaces_running_sync(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    m = mgr_mod.SyncManager()
    first_started = asyncio.Event()
    second_release = asyncio.Event()
    cancelled = {"first": False}
    calls = {"n": 0}

    async def fake_run_all(db: Any, report: Any = None) -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] == 1:
            first_started.set()
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                cancelled["first"] = True
                raise
        else:
            await second_release.wait()
        return {}

    monkeypatch.setattr(scheduler, "run_all", fake_run_all)

    await m.start(_DB, cancel_existing=False)
    await first_started.wait()

    # "sync now" pre-empts the first run and starts a fresh one
    assert await m.start(_DB, cancel_existing=True) == "started"
    assert cancelled["first"] is True
    assert m.running is True

    second_release.set()
    assert m._task is not None
    await m._task
    assert m.running is False
    assert calls["n"] == 2
