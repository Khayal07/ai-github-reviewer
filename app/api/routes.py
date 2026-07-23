"""Read-only JSON API backing the dashboard: stats, reviews, repos, evals."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import EvalRun, Finding, Repo, Review
from app.db.session import get_db

router = APIRouter(prefix="/api", tags=["api"])


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _review_summary(review: Review, finding_count: int | None = None) -> dict:
    return {
        "id": review.id,
        "repo_full_name": review.repo_full_name,
        "pr_number": review.pr_number,
        "head_sha": review.head_sha,
        "status": review.status,
        "verdict": review.verdict,
        "counts": review.counts or {},
        "latency_ms": review.latency_ms,
        "finding_count": finding_count,
        "created_at": _iso(review.created_at),
    }


@router.get("/stats")
def stats(db: Session = Depends(get_db)) -> dict:
    total_reviews = db.scalar(select(func.count(Review.id))) or 0
    total_repos = db.scalar(select(func.count(Repo.id))) or 0
    total_findings = db.scalar(select(func.count(Finding.id))) or 0
    verdicts = dict(
        db.execute(
            select(Review.verdict, func.count(Review.id))
            .where(Review.verdict.is_not(None))
            .group_by(Review.verdict)
        ).all()
    )
    avg_latency = db.scalar(
        select(func.avg(Review.latency_ms)).where(Review.latency_ms.is_not(None))
    )
    return {
        "total_reviews": total_reviews,
        "total_repos": total_repos,
        "total_findings": total_findings,
        "verdicts": verdicts,
        "avg_latency_ms": round(avg_latency, 1) if avg_latency else None,
    }


@router.get("/reviews")
def list_reviews(
    limit: int = Query(default=50, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    reviews = (
        db.execute(select(Review).order_by(Review.created_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    return [_review_summary(r) for r in reviews]


@router.get("/reviews/{review_id}")
def get_review(review_id: int, db: Session = Depends(get_db)) -> dict:
    review = db.get(Review, review_id)
    if review is None:
        raise HTTPException(status_code=404, detail="Review not found")
    findings = [
        {
            "id": f.id,
            "file": f.file,
            "line": f.line,
            "end_line": f.end_line,
            "side": f.side,
            "severity": f.severity,
            "pass_type": f.pass_type,
            "title": f.title,
            "message": f.message,
            "suggestion": f.suggestion,
            "confidence": f.confidence,
        }
        for f in review.findings
    ]
    return {**_review_summary(review, len(findings)), "findings": findings}


@router.get("/repos")
def list_repos(db: Session = Depends(get_db)) -> list[dict]:
    counts = dict(
        db.execute(
            select(Review.repo_full_name, func.count(Review.id)).group_by(
                Review.repo_full_name
            )
        ).all()
    )
    repos = db.execute(select(Repo).order_by(Repo.full_name)).scalars().all()
    result = [
        {
            "id": r.id,
            "full_name": r.full_name,
            "installation_id": r.installation_id,
            "review_count": counts.get(r.full_name, 0),
            "created_at": _iso(r.created_at),
        }
        for r in repos
    ]
    # Include repos seen only via reviews (e.g. Action runs without an install).
    known = {r["full_name"] for r in result}
    for name, count in counts.items():
        if name not in known:
            result.append(
                {
                    "id": None,
                    "full_name": name,
                    "installation_id": None,
                    "review_count": count,
                    "created_at": None,
                }
            )
    return result


@router.get("/eval")
def list_eval_runs(
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
) -> list[dict]:
    runs = (
        db.execute(select(EvalRun).order_by(EvalRun.created_at.desc()).limit(limit))
        .scalars()
        .all()
    )
    return [
        {
            "id": run.id,
            "num_cases": run.num_cases,
            "recall": run.recall,
            "precision": run.precision,
            "avg_latency_ms": run.avg_latency_ms,
            "report": run.report,
            "created_at": _iso(run.created_at),
        }
        for run in runs
    ]
