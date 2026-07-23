"""GitHub App webhook: receive pull_request events and review in the background.

The handler validates the HMAC signature, acknowledges quickly, and offloads
the review to a background task (which runs in FastAPI's threadpool, so its
synchronous GitHub HTTP calls don't block the event loop).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from app.config import get_settings
from app.github.auth import get_installation_token
from app.github.client import GitHubClient
from app.db.session import SessionLocal
from app.reviewer import ReviewRequest, run_review
from app.store import complete_review, create_review, fail_review

logger = logging.getLogger("ai_reviewer.webhook")

router = APIRouter(tags=["github"])

_REVIEWABLE_ACTIONS = {"opened", "synchronize", "reopened", "ready_for_review"}


def verify_signature(secret: str, body: bytes, signature_header: str | None) -> bool:
    """Constant-time verification of GitHub's X-Hub-Signature-256 header."""
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _installation_token(settings, installation_id: int | None) -> str | None:
    """Mint an installation token, or fall back to a configured PAT."""
    private_key = settings.resolve_app_private_key()
    if installation_id and settings.github_app_id and private_key:
        try:
            return get_installation_token(
                settings.github_app_id, private_key, installation_id
            ).token
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to mint installation token: %s", exc)
    return settings.github_token


def _process_review(req: ReviewRequest, installation_id: int | None) -> None:
    """Run one review cycle and record it. Executed in a threadpool."""
    settings = get_settings()
    token = _installation_token(settings, installation_id)
    if not token:
        logger.error("No GitHub credentials available; skipping review.")
        return

    client = GitHubClient(token)
    db = SessionLocal()
    review = create_review(
        db, f"{req.owner}/{req.repo}", req.pr_number, req.head_sha, installation_id
    )
    started = time.monotonic()
    try:
        result = asyncio.run(run_review(client, req, settings))
        latency_ms = int((time.monotonic() - started) * 1000)
        complete_review(db, review, result, latency_ms)
        logger.info(
            "Reviewed %s/%s#%s -> %s (%d findings)",
            req.owner, req.repo, req.pr_number, result.verdict.value,
            len(result.findings),
        )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Review failed for %s#%s", req.repo, req.pr_number)
        fail_review(db, review, str(exc))
    finally:
        client.close()
        db.close()


@router.post("/webhook")
async def github_webhook(
    request: Request,
    background: BackgroundTasks,
    x_github_event: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
) -> dict:
    body = await request.body()
    settings = get_settings()

    if settings.github_webhook_secret:
        if not verify_signature(settings.github_webhook_secret, body, x_hub_signature_256):
            raise HTTPException(status_code=401, detail="Invalid signature")

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON") from None

    if x_github_event == "ping":
        return {"status": "pong"}

    if x_github_event != "pull_request":
        return {"status": "ignored", "event": x_github_event}

    if payload.get("action") not in _REVIEWABLE_ACTIONS:
        return {"status": "ignored", "action": payload.get("action")}

    pr = payload["pull_request"]
    repo = payload["repository"]
    req = ReviewRequest(
        owner=repo["owner"]["login"],
        repo=repo["name"],
        pr_number=pr["number"],
        head_sha=pr["head"]["sha"],
    )
    installation_id = (payload.get("installation") or {}).get("id")
    background.add_task(_process_review, req, installation_id)
    return {"status": "queued", "pr": req.pr_number}
