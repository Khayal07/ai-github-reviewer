"""FastAPI application entrypoint.

Serves the GitHub webhook, the JSON API for the dashboard, and (in production)
the built React frontend. Additional routers are mounted in later phases.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api.routes import router as api_router
from app.config import get_settings
from app.db.session import init_db
from app.webhook import router as webhook_router

_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

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
app.include_router(api_router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    """Liveness/readiness probe."""
    return {"status": "ok", "version": __version__, "env": settings.app_env}


# Serve the built React dashboard when present (production image / after
# `npm run build`). API, webhook, health, and docs routes above take
# precedence; the catch-all returns index.html so client-side routes survive a
# hard refresh. When the bundle is absent (pure API/dev mode) a JSON root is
# served instead.
if _FRONTEND_DIST.is_dir():
    app.mount(
        "/assets",
        StaticFiles(directory=_FRONTEND_DIST / "assets"),
        name="assets",
    )
    _INDEX_HTML = (_FRONTEND_DIST / "index.html").read_text(encoding="utf-8")

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa(full_path: str):
        candidate = _FRONTEND_DIST / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return HTMLResponse(_INDEX_HTML)
else:

    @app.get("/", tags=["meta"])
    def root() -> dict:
        return {"service": "ai-github-reviewer", "docs": "/docs", "health": "/health"}
