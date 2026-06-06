"""In-memory coordinator for ingest runs.

Tracks a single active sync (so only one runs at a time), exposes live
per-connector progress for the dashboard, and supports cancelling the
running sync when a new "sync now" is requested.
"""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

# Connector lifecycle states reported during a run.
PENDING = "pending"
RUNNING = "running"
DONE = "done"
ERROR = "error"
CANCELLED = "cancelled"


class SyncManager:
    def __init__(self) -> None:
        self.running: bool = False
        self.cancelled: bool = False
        self.started_at: datetime | None = None
        self.finished_at: datetime | None = None
        self.connectors: dict[str, dict[str, Any]] = {}
        self._task: asyncio.Task[Any] | None = None

    # ------------------------------------------------------------------
    # progress reporting — passed as a callback into the scheduler
    # ------------------------------------------------------------------
    def report(
        self,
        connector: str,
        state: str,
        *,
        count: int | None = None,
        error: str | None = None,
    ) -> None:
        entry = self.connectors.setdefault(connector, {})
        entry["state"] = state
        if count is not None:
            entry["count"] = count
        if error is not None:
            entry["error"] = error
        entry["updated_at"] = datetime.now(UTC)

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    async def start(
        self,
        db: AsyncIOMotorDatabase,
        *,
        cancel_existing: bool,
    ) -> str:
        """Begin a sync. If one is already running, either cancel-and-replace
        it (manual "sync now") or skip (scheduled tick), per cancel_existing.
        """
        if self.running:
            if not cancel_existing:
                return "busy"
            await self.cancel()
        self.running = True
        self.cancelled = False
        self.started_at = datetime.now(UTC)
        self.finished_at = None
        self.connectors = {}
        self._task = asyncio.create_task(self._run(db))
        return "started"

    async def cancel(self) -> None:
        task = self._task
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task

    async def _run(self, db: AsyncIOMotorDatabase) -> None:
        # Imported here to avoid an import cycle (scheduler does not know
        # about the manager).
        from atlaslens.ingest.scheduler import run_all

        try:
            results = await run_all(db, report=self.report)
            logger.info("Sync complete: %s", results)
        except asyncio.CancelledError:
            self.cancelled = True
            for entry in self.connectors.values():
                if entry.get("state") in (PENDING, RUNNING):
                    entry["state"] = CANCELLED
                    entry["updated_at"] = datetime.now(UTC)
            logger.info("Sync cancelled")
            raise
        except Exception:
            logger.exception("Sync failed")
        finally:
            self.running = False
            self.finished_at = datetime.now(UTC)

    def snapshot(self) -> dict[str, Any]:
        def _iso(v: Any) -> Any:
            return v.isoformat() if isinstance(v, datetime) else v

        return {
            "running": self.running,
            "cancelled": self.cancelled,
            "started_at": _iso(self.started_at),
            "finished_at": _iso(self.finished_at),
            "connectors": {
                cid: {k: _iso(v) for k, v in entry.items()}
                for cid, entry in self.connectors.items()
            },
        }


# Module-level singleton shared by the API route and the scheduler ticks.
manager = SyncManager()
