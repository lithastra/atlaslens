from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from atlaslens.api.routes import health, sync
from atlaslens.db import close_db, connect_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await connect_db()
    yield
    await close_db()


app = FastAPI(
    title="AtlasLens",
    description="Atlassian audit & activity dashboard",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(sync.router)
