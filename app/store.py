"""Persistence helpers for review runs, findings, and eval runs."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Finding as FindingRow
from app.db.models import Repo, Review
from app.review.schema import ReviewResult


def get_or_create_repo(
    db: Session, full_name: str, installation_id: int | None = None
) -> Repo:
    repo = db.execute(
        select(Repo).where(Repo.full_name == full_name)
    ).scalar_one_or_none()
    if repo is None:
        repo = Repo(full_name=full_name, installation_id=installation_id)
        db.add(repo)
        db.flush()
    elif installation_id and repo.installation_id != installation_id:
        repo.installation_id = installation_id
    return repo


def create_review(
    db: Session,
    repo_full_name: str,
    pr_number: int,
    head_sha: str | None,
    installation_id: int | None = None,
) -> Review:
    """Create a review row in the `running` state."""
    repo = get_or_create_repo(db, repo_full_name, installation_id)
    review = Review(
        repo_id=repo.id,
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        head_sha=head_sha,
        status="running",
    )
    db.add(review)
    db.commit()
    db.refresh(review)
    return review


def complete_review(
    db: Session, review: Review, result: ReviewResult, latency_ms: int
) -> Review:
    """Mark a review completed and persist its findings."""
    review.status = "completed"
    review.verdict = result.verdict.value
    review.counts = result.counts
    review.latency_ms = latency_ms
    for f in result.findings:
        db.add(
            FindingRow(
                review_id=review.id,
                file=f.file,
                line=f.line,
                end_line=f.end_line,
                side=f.side,
                severity=f.severity.value,
                pass_type=f.pass_type.value,
                title=f.title,
                message=f.message,
                suggestion=f.suggestion,
                confidence=f.confidence,
            )
        )
    db.commit()
    db.refresh(review)
    return review


def fail_review(db: Session, review: Review, error: str) -> Review:
    review.status = "failed"
    review.error = error[:4000]
    db.commit()
    db.refresh(review)
    return review
