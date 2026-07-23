"""FastAPI application entrypoint.

Serves the GitHub webhook, the JSON API for the dashboard, and (in production)
the built React frontend. Additional routers are mounted in later phases.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.config import get_settings
from app.db.session import init_db
from app.webhook import router as webhook_router

settings = get_settings()
logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger("ai_reviewer")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # In development we create tables directly; production relies on Alembic.
    if not settings.is_production:
        init_db()
        logger.info("Database tables ensured (development mode).")
    yield


app = FastAPI(
    title="AI GitHub PR Reviewer",
    version=__version__,
    summary="Automated multi-pass pull-request reviewer.",
    lifespan=lifespan,
)


app.include_router(webhook_router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness/readiness probe."""
    return {"status": "ok", "version": __version__, "env": settings.app_env}


@app.get("/", tags=["meta"])
def root() -> dict:
    return {"service": "ai-github-reviewer", "docs": "/docs", "health": "/health"}
