"""CLI entrypoint for the GitHub Action wrapper.

Runs one review cycle for the PR in the current Actions event context, using
`GITHUB_TOKEN` for API access. Exits non-zero when the verdict requests
changes so the reviewer can gate a CI check.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys

from app.config import get_settings
from app.github.client import GitHubClient
from app.reviewer import ReviewRequest, run_review
from app.review.schema import Verdict


def _load_event() -> dict:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _build_request() -> ReviewRequest | None:
    """Derive the PR reference from the Actions event or explicit env vars."""
    event = _load_event()
    pr = event.get("pull_request")
    repo = event.get("repository", {})

    if pr and repo:
        owner = repo["owner"]["login"]
        name = repo["name"]
        return ReviewRequest(
            owner=owner, repo=name, pr_number=pr["number"], head_sha=pr["head"]["sha"]
        )

    # Fallback: explicit inputs (e.g. manual runs).
    full = os.environ.get("GITHUB_REPOSITORY", "")
    pr_number = os.environ.get("PR_NUMBER")
    if "/" in full and pr_number:
        owner, name = full.split("/", 1)
        return ReviewRequest(
            owner=owner,
            repo=name,
            pr_number=int(pr_number),
            head_sha=os.environ.get("HEAD_SHA"),
        )
    return None


def main() -> int:
    settings = get_settings()
    if not settings.github_token:
        print("::error::GITHUB_TOKEN is not set.", file=sys.stderr)
        return 2

    req = _build_request()
    if req is None:
        print("::error::Could not determine the pull request to review.", file=sys.stderr)
        return 2

    client = GitHubClient(settings.github_token)
    try:
        result = asyncio.run(run_review(client, req, settings))
    finally:
        client.close()

    print(f"Verdict: {result.verdict.value} ({len(result.findings)} findings)")
    for sev, count in result.counts.items():
        if count:
            print(f"  {sev}: {count}")

    return 1 if result.verdict == Verdict.request_changes else 0


if __name__ == "__main__":
    raise SystemExit(main())
