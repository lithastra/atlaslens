import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from atlaslens.api.routes import (
    aggregations,
    auth,
    events,
    exports,
    health,
    items,
    reports,
    sync,
)
from atlaslens.config import settings
from atlaslens.db import close_db, connect_db, get_db
from atlaslens.ingest.scheduler import run_all
from atlaslens.reports.generator import run_scheduled_reports

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None


async def _ingest_tick() -> None:
    try:
        db = get_db()
        results = await run_all(db)
        logger.info("Ingest cycle complete: %s", results)
    except Exception:
        logger.exception("Ingest cycle failed")


async def _reports_tick() -> None:
    try:
        db = get_db()
        count = await run_scheduled_reports(db)
        if count:
            logger.info("Generated %d scheduled reports", count)
    except Exception:
        logger.exception("Scheduled reports tick failed")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _scheduler
    await connect_db()

    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _ingest_tick,
        "interval",
        minutes=settings.ingest_interval_minutes,
        id="ingest",
        replace_existing=True,
    )
    _scheduler.add_job(
        _reports_tick,
        "cron",
        hour=1,
        minute=0,
        id="scheduled_reports",
        replace_existing=True,
    )
    _scheduler.start()
    logger.info(
        "Ingest scheduler started (every %d min)",
        settings.ingest_interval_minutes,
    )

    asyncio.create_task(_ingest_tick())

    yield

    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    await close_db()


app = FastAPI(
    title="AtlasLens",
    description="Atlassian audit & activity dashboard",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(events.router)
app.include_router(aggregations.router)
app.include_router(items.router)
app.include_router(exports.router)
app.include_router(reports.router)
app.include_router(sync.router)
