"""ORM models: repositories, reviews, findings, and eval runs."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Repo(Base):
    """A repository the reviewer is installed on / has reviewed."""

    __tablename__ = "repos"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    installation_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    reviews: Mapped[list[Review]] = relationship(
        back_populates="repo", cascade="all, delete-orphan"
    )


class Review(Base):
    """A single review run against one PR head SHA."""

    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    repo_id: Mapped[int | None] = mapped_column(
        ForeignKey("repos.id", ondelete="CASCADE"), nullable=True
    )
    repo_full_name: Mapped[str] = mapped_column(String(255), index=True)
    pr_number: Mapped[int] = mapped_column(Integer, index=True)
    head_sha: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # queued | running | completed | failed
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    # approve | comment | request_changes
    verdict: Mapped[str | None] = mapped_column(String(20), nullable=True)
    counts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    repo: Mapped[Repo | None] = relationship(back_populates="reviews")
    findings: Mapped[list[Finding]] = relationship(
        back_populates="review", cascade="all, delete-orphan"
    )


class Finding(Base):
    """A single issue produced by a review pass."""

    __tablename__ = "findings"

    id: Mapped[int] = mapped_column(primary_key=True)
    review_id: Mapped[int] = mapped_column(
        ForeignKey("reviews.id", ondelete="CASCADE"), index=True
    )
    file: Mapped[str] = mapped_column(String(512))
    line: Mapped[int] = mapped_column(Integer)
    end_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    side: Mapped[str] = mapped_column(String(8), default="RIGHT")
    severity: Mapped[str] = mapped_column(String(16), index=True)
    pass_type: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(255))
    message: Mapped[str] = mapped_column(Text)
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)

    review: Mapped[Review] = relationship(back_populates="findings")


class EvalRun(Base):
    """A benchmark evaluation run, summarising recall / precision / latency."""

    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    num_cases: Mapped[int] = mapped_column(Integer, default=0)
    recall: Mapped[float | None] = mapped_column(Float, nullable=True)
    precision: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    report: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
