"""Tests for the webhook signature check, event routing, and DB logging."""

import hashlib
import hmac
import json

from fastapi.testclient import TestClient

import app.webhook as webhook
from app.db.session import SessionLocal, init_db
from app.main import app
from app.review.schema import (
    Finding,
    PassType,
    ReviewResult,
    Severity,
    Verdict,
    compute_counts,
)
from app.store import complete_review, create_review, fail_review

client = TestClient(app)


def test_verify_signature():
    secret = "s3cr3t"
    body = b'{"hello": "world"}'
    good = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert webhook.verify_signature(secret, body, good) is True
    assert webhook.verify_signature(secret, body, "sha256=deadbeef") is False
    assert webhook.verify_signature(secret, body, None) is False


def test_ping_event():
    resp = client.post("/webhook", headers={"X-GitHub-Event": "ping"}, json={})
    assert resp.status_code == 200
    assert resp.json()["status"] == "pong"


def test_non_pr_event_ignored():
    resp = client.post("/webhook", headers={"X-GitHub-Event": "push"}, json={})
    assert resp.json()["status"] == "ignored"


def test_pull_request_event_queues_background_task(monkeypatch):
    calls = []
    monkeypatch.setattr(
        webhook, "_process_review", lambda req, inst: calls.append((req, inst))
    )
    payload = {
        "action": "opened",
        "pull_request": {"number": 7, "head": {"sha": "abc123"}},
        "repository": {"name": "r", "owner": {"login": "o"}},
        "installation": {"id": 99},
    }
    resp = client.post(
        "/webhook", headers={"X-GitHub-Event": "pull_request"}, json=payload
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "queued", "pr": 7}
    # TestClient runs background tasks after the response.
    assert len(calls) == 1
    req, inst = calls[0]
    assert req.owner == "o" and req.repo == "r" and req.pr_number == 7
    assert inst == 99


def test_store_logs_review_lifecycle():
    init_db()
    db = SessionLocal()
    try:
        review = create_review(db, "o/r", 5, "sha", installation_id=1)
        assert review.status == "running"

        findings = [
            Finding(
                file="a.py", line=2, severity=Severity.high,
                pass_type=PassType.correctness, title="t", message="m",
            )
        ]
        result = ReviewResult(
            findings=findings, verdict=Verdict.request_changes,
            counts=compute_counts(findings),
        )
        complete_review(db, review, result, latency_ms=1234)

        assert review.status == "completed"
        assert review.verdict == "request_changes"
        assert review.latency_ms == 1234
        assert len(review.findings) == 1

        failed = create_review(db, "o/r", 6, "sha2")
        fail_review(db, failed, "boom")
        assert failed.status == "failed" and failed.error == "boom"
    finally:
        db.close()
