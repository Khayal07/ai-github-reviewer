"""End-to-end review orchestration shared by the webhook and the Action.

Given a PR reference and an authenticated GitHub client, this fetches the
config and diff, runs the review engine, and posts the result back. It has no
database or transport concerns of its own, so both entry points (webhook bot
and CLI Action) reuse it unchanged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import Settings
from app.config_schema import ReviewerConfig
from app.github.client import GitHubClient
from app.github.comments import post_review
from app.github.diff import parse_files
from app.review.context import gather_context, render_for_prompt
from app.review.engine import ReviewEngine
from app.review.llm import LLMClient, build_llm_client
from app.review.passes import build_passes
from app.review.schema import ReviewResult, Verdict, compute_counts

logger = logging.getLogger("ai_reviewer.reviewer")

CONFIG_FILENAME = ".ai-reviewer.yml"


@dataclass
class ReviewRequest:
    owner: str
    repo: str
    pr_number: int
    head_sha: str | None = None


async def run_review(
    client: GitHubClient,
    req: ReviewRequest,
    settings: Settings,
    *,
    llm: LLMClient | None = None,
    dry_run: bool = False,
) -> ReviewResult:
    """Fetch, review, and (unless dry-run) post a review for one PR."""
    owner, repo, number = req.owner, req.repo, req.pr_number

    # 1. Per-repo config (missing file -> defaults).
    cfg_text = client.get_file_content(owner, repo, CONFIG_FILENAME, ref=req.head_sha)
    config = ReviewerConfig.load(cfg_text)

    # 2. Changed files, minus ignored paths and binary (patch-less) files.
    files = client.list_pull_files(owner, repo, number)
    files = [
        f
        for f in files
        if f.get("patch") and not config.is_ignored(f.get("filename", ""))
    ]

    if not files:
        result = ReviewResult(
            findings=[], verdict=Verdict.approve, counts=compute_counts([])
        )
        if not dry_run:
            client.create_issue_comment(
                owner, repo, number,
                "## 🤖 AI PR Review\n\nNo reviewable changes found "
                "(only ignored or binary files).",
            )
        return result

    if len(files) > config.max_files:
        result = ReviewResult(
            findings=[], verdict=Verdict.comment, counts=compute_counts([])
        )
        if not dry_run:
            client.create_issue_comment(
                owner, repo, number,
                f"## 🤖 AI PR Review\n\nSkipped: this PR changes "
                f"{len(files)} files, above the configured limit of "
                f"{config.max_files}.",
            )
        return result

    # 3. Parse the diff and gather surrounding context.
    diff = parse_files(files)

    def fetch(path: str) -> str | None:
        return client.get_file_content(owner, repo, path, ref=req.head_sha)

    contents = gather_context(diff, fetch)
    rendered = render_for_prompt(diff, contents)

    # 4. Build the engine (config LLM override wins over service defaults).
    if llm is None:
        provider = config.llm.provider or settings.llm_provider
        model = config.llm.model or settings.llm_model
        llm = build_llm_client(
            provider,
            model,
            openai_api_key=settings.openai_api_key,
            anthropic_api_key=settings.anthropic_api_key,
        )
    engine = ReviewEngine(llm, build_passes(config.passes))

    # 5. Run the passes and post the review.
    result = await engine.review(
        diff,
        rendered,
        block_severity=config.block_severity,
        min_confidence=config.min_confidence,
    )
    if not dry_run:
        post_review(client, owner, repo, number, result, diff, head_sha=req.head_sha)
    return result
