"""Findings schema and pure aggregation helpers (severity, dedupe, verdict).

These functions are deliberately side-effect free so the verdict / threshold
logic can be unit tested without any LLM or GitHub calls.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Severity(str, Enum):
    info = "info"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class PassType(str, Enum):
    correctness = "correctness"
    security = "security"
    style = "style"
    tests = "tests"


class Verdict(str, Enum):
    approve = "approve"
    comment = "comment"
    request_changes = "request_changes"


_SEVERITY_RANK: dict[Severity, int] = {
    Severity.info: 0,
    Severity.low: 1,
    Severity.medium: 2,
    Severity.high: 3,
    Severity.critical: 4,
}


class Finding(BaseModel):
    file: str
    line: int
    end_line: int | None = None
    side: Literal["RIGHT", "LEFT"] = "RIGHT"
    severity: Severity
    pass_type: PassType
    title: str
    message: str
    suggestion: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class ReviewResult(BaseModel):
    findings: list[Finding]
    verdict: Verdict
    counts: dict[str, int]


def severity_rank(severity: Severity | str) -> int:
    """Ordinal rank of a severity (higher = more severe)."""
    if isinstance(severity, str):
        severity = Severity(severity)
    return _SEVERITY_RANK[severity]


def meets_threshold(severity: Severity | str, threshold: Severity | str) -> bool:
    """True if `severity` is at or above `threshold`."""
    return severity_rank(severity) >= severity_rank(threshold)


def compute_counts(findings: list[Finding]) -> dict[str, int]:
    """Count findings by severity, always returning all severity keys."""
    counts = {sev.value: 0 for sev in Severity}
    for f in findings:
        counts[f.severity.value] += 1
    return counts


def dedupe_findings(findings: list[Finding]) -> list[Finding]:
    """Collapse findings sharing (file, side, line, pass_type).

    Keeps the highest-severity, then highest-confidence finding for each key,
    preserving first-seen order.
    """
    best: dict[tuple, Finding] = {}
    order: list[tuple] = []
    for f in findings:
        key = (f.file, f.side, f.line, f.pass_type)
        current = best.get(key)
        if current is None:
            best[key] = f
            order.append(key)
            continue
        challenger = (severity_rank(f.severity), f.confidence)
        incumbent = (severity_rank(current.severity), current.confidence)
        if challenger > incumbent:
            best[key] = f
    return [best[k] for k in order]


def merge_overlapping(findings: list[Finding], window: int = 1) -> list[Finding]:
    """Collapse findings that describe the same spot across different passes.

    Models often report one issue (a hardcoded key, a SQL-injection line) from
    several passes at the same or an adjacent line. This groups findings on the
    same file/side whose lines fall within `window`, keeping the highest
    severity (then confidence) representative. Findings more than `window` lines
    apart stay separate, so genuinely distinct issues are preserved.
    """
    groups: dict[tuple, list[Finding]] = {}
    order: list[tuple] = []
    for f in findings:
        key = (f.file, f.side)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(f)

    merged: list[Finding] = []
    for key in order:
        items = sorted(groups[key], key=lambda f: f.line)
        clusters: list[list[Finding]] = []
        for f in items:
            for cluster in clusters:
                if any(abs(f.line - g.line) <= window for g in cluster):
                    cluster.append(f)
                    break
            else:
                clusters.append([f])
        for cluster in clusters:
            merged.append(
                max(cluster, key=lambda f: (severity_rank(f.severity), f.confidence))
            )

    merged.sort(key=lambda f: (f.file, f.line))
    return merged


def compute_verdict(findings: list[Finding], block_severity: Severity | str) -> Verdict:
    """Approve when clean, request changes when any finding meets the block
    threshold, otherwise comment."""
    if not findings:
        return Verdict.approve
    if any(meets_threshold(f.severity, block_severity) for f in findings):
        return Verdict.request_changes
    return Verdict.comment
