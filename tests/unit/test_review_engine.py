"""Unit tests for the findings schema helpers and the review engine."""

import pytest

from app.github.diff import parse_files
from app.review.engine import ReviewEngine
from app.review.llm import LLMClient
from app.review.schema import (
    Finding,
    PassType,
    Severity,
    Verdict,
    compute_counts,
    compute_verdict,
    dedupe_findings,
    meets_threshold,
    merge_overlapping,
    severity_rank,
)

PATCH = """@@ -1,3 +1,5 @@
 def f():
-    return 1
+    x = 1
+    return x
 # end"""


def _finding(file="app.py", line=2, severity=Severity.high, pass_type=PassType.correctness,
             confidence=0.9, title="t", message="m"):
    return Finding(
        file=file, line=line, severity=severity, pass_type=pass_type,
        confidence=confidence, title=title, message=message,
    )


# --- pure helpers ---------------------------------------------------------

def test_severity_rank_and_threshold():
    assert severity_rank("critical") > severity_rank("high") > severity_rank("low")
    assert meets_threshold(Severity.high, Severity.high) is True
    assert meets_threshold(Severity.medium, Severity.high) is False
    assert meets_threshold("critical", "high") is True


def test_compute_counts_covers_all_severities():
    counts = compute_counts([_finding(severity=Severity.high), _finding(severity=Severity.low)])
    assert counts["high"] == 1 and counts["low"] == 1
    assert counts["critical"] == 0 and counts["info"] == 0


def test_verdict_approve_comment_request_changes():
    assert compute_verdict([], Severity.high) == Verdict.approve
    assert compute_verdict([_finding(severity=Severity.low)], Severity.high) == Verdict.comment
    assert compute_verdict([_finding(severity=Severity.high)], Severity.high) == Verdict.request_changes
    # threshold is configurable
    assert compute_verdict([_finding(severity=Severity.medium)], Severity.medium) == Verdict.request_changes


def test_dedupe_keeps_highest_severity_then_confidence():
    low = _finding(severity=Severity.low, confidence=0.9)
    high = _finding(severity=Severity.high, confidence=0.5)
    deduped = dedupe_findings([low, high])
    assert len(deduped) == 1
    assert deduped[0].severity == Severity.high

    # Different pass_type at same line is NOT a duplicate.
    a = _finding(pass_type=PassType.correctness)
    b = _finding(pass_type=PassType.security)
    assert len(dedupe_findings([a, b])) == 2


def test_merge_overlapping_collapses_cross_pass_same_and_adjacent_lines():
    findings = [
        _finding(line=7, pass_type=PassType.security, severity=Severity.high, confidence=0.95),
        _finding(line=7, pass_type=PassType.correctness, severity=Severity.critical, confidence=1.0),
        _finding(line=7, pass_type=PassType.style, severity=Severity.medium),
        _finding(line=11, pass_type=PassType.security, severity=Severity.medium),
        _finding(line=12, pass_type=PassType.correctness, severity=Severity.high),  # adjacent
    ]
    merged = merge_overlapping(findings, window=1)
    # line 7 cluster -> 1 (keeps critical); lines 11/12 cluster -> 1 (keeps high)
    assert len(merged) == 2
    assert merged[0].line == 7 and merged[0].severity == Severity.critical
    assert merged[1].severity == Severity.high


def test_merge_overlapping_keeps_distinct_issues_apart():
    findings = [
        _finding(file="a.py", line=4, severity=Severity.high),
        _finding(file="a.py", line=7, severity=Severity.critical),
        _finding(file="b.py", line=4, severity=Severity.low),
    ]
    merged = merge_overlapping(findings, window=1)
    assert len(merged) == 3  # different lines (>1 apart) and different files stay


# --- engine ---------------------------------------------------------------

class _StubLLM(LLMClient):
    def __init__(self, per_pass: dict[PassType, list[Finding]]):
        self.per_pass = per_pass

    async def review(self, *, system, user, pass_type):
        return list(self.per_pass.get(pass_type, []))


class _StubPass:
    def __init__(self, name, pass_type):
        self.name = name
        self.pass_type = pass_type

    async def run(self, rendered_diff, llm):
        return await llm.review(system="", user=rendered_diff, pass_type=self.pass_type)


@pytest.mark.asyncio
async def test_engine_filters_confidence_and_hallucinated_files():
    diff = parse_files([{"filename": "app.py", "status": "modified", "patch": PATCH}])
    llm = _StubLLM({
        PassType.correctness: [
            _finding(line=2, severity=Severity.high, confidence=0.9),
            _finding(line=3, severity=Severity.low, confidence=0.2),  # dropped: low conf
        ],
        PassType.security: [
            _finding(file="ghost.py", line=1, confidence=0.95),  # dropped: not in diff
        ],
    })
    engine = ReviewEngine(llm, [
        _StubPass("correctness", PassType.correctness),
        _StubPass("security", PassType.security),
    ])

    result = await engine.review(diff, "rendered", block_severity=Severity.high, min_confidence=0.6)

    assert len(result.findings) == 1
    assert result.findings[0].line == 2
    assert result.verdict == Verdict.request_changes
    assert result.counts["high"] == 1


@pytest.mark.asyncio
async def test_engine_survives_a_failing_pass():
    diff = parse_files([{"filename": "app.py", "status": "modified", "patch": PATCH}])

    class _BoomPass(_StubPass):
        async def run(self, rendered_diff, llm):
            raise RuntimeError("pass exploded")

    llm = _StubLLM({PassType.style: [_finding(severity=Severity.low, pass_type=PassType.style)]})
    engine = ReviewEngine(llm, [
        _BoomPass("correctness", PassType.correctness),
        _StubPass("style", PassType.style),
    ])

    result = await engine.review(diff, "rendered", min_confidence=0.6)
    assert result.verdict == Verdict.comment
    assert len(result.findings) == 1
