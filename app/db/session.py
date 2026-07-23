"""SQLAlchemy engine, session factory, and declarative base."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


def _make_engine():
    settings = get_settings()
    url = settings.database_url
    connect_args = {}
    if url.startswith("sqlite"):
        # Needed so a SQLite connection can be shared across threads
        # (FastAPI background tasks run in a threadpool).
        connect_args = {"check_same_thread": False}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


engine = _make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables from metadata (used in dev / tests; prod uses Alembic)."""
    # Import models so they register on the metadata before create_all.
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
