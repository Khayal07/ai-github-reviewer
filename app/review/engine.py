"""Review orchestration: run passes concurrently, then aggregate.

The engine is intentionally free of GitHub/DB concerns — it takes a parsed
diff plus rendered context and returns a `ReviewResult`. Filtering, dedupe,
and verdict all reuse the pure helpers in `schema.py`.
"""

from __future__ import annotations

import asyncio
import logging

from app.github.diff import ParsedDiff
from app.review.llm import LLMClient
from app.review.passes.base import BasePass
from app.review.schema import (
    Finding,
    ReviewResult,
    Severity,
    compute_counts,
    compute_verdict,
    dedupe_findings,
    merge_overlapping,
)

logger = logging.getLogger("ai_reviewer.engine")


class ReviewEngine:
    def __init__(self, llm: LLMClient, passes: list[BasePass]) -> None:
        self.llm = llm
        self.passes = passes

    async def review(
        self,
        diff: ParsedDiff,
        rendered_diff: str,
        *,
        block_severity: Severity | str = Severity.high,
        min_confidence: float = 0.6,
    ) -> ReviewResult:
        results = await asyncio.gather(
            *(p.run(rendered_diff, self.llm) for p in self.passes),
            return_exceptions=True,
        )

        findings: list[Finding] = []
        for pass_obj, result in zip(self.passes, results, strict=True):
            if isinstance(result, Exception):
                logger.warning("Pass %s failed: %s", pass_obj.name, result)
                continue
            findings.extend(result)

        findings = [
            f
            for f in findings
            if f.confidence >= min_confidence and diff.get(f.file) is not None
        ]
        findings = dedupe_findings(findings)
        # Collapse the same issue reported by multiple passes at nearby lines.
        findings = merge_overlapping(findings)

        return ReviewResult(
            findings=findings,
            verdict=compute_verdict(findings, block_severity),
            counts=compute_counts(findings),
        )
