"""Scoring: match produced findings to ground truth and aggregate metrics."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from app.review.schema import Finding

LINE_TOLERANCE = 2


def _match(finding: Finding, gt: dict) -> bool:
    return (
        finding.file == gt["file"]
        and finding.pass_type.value == gt["pass_type"]
        and abs(finding.line - int(gt["line"])) <= LINE_TOLERANCE
    )


@dataclass
class CaseScore:
    name: str
    tp: int = 0
    fp: int = 0
    fn: int = 0
    latency_ms: float = 0.0
    per_pass: dict[str, dict[str, int]] = field(default_factory=dict)


def score_case(
    name: str,
    produced: list[Finding],
    ground_truth: list[dict],
    latency_ms: float,
) -> CaseScore:
    """Greedily match produced findings to ground truth for one case."""
    used = [False] * len(ground_truth)
    per_pass: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fp": 0, "fn": 0}
    )
    tp = fp = 0

    for f in produced:
        matched = False
        for i, gt in enumerate(ground_truth):
            if not used[i] and _match(f, gt):
                used[i] = True
                matched = True
                break
        bucket = per_pass[f.pass_type.value]
        if matched:
            tp += 1
            bucket["tp"] += 1
        else:
            fp += 1
            bucket["fp"] += 1

    fn = used.count(False)
    for i, gt in enumerate(ground_truth):
        if not used[i]:
            per_pass[gt["pass_type"]]["fn"] += 1

    return CaseScore(
        name=name,
        tp=tp,
        fp=fp,
        fn=fn,
        latency_ms=latency_ms,
        per_pass={k: dict(v) for k, v in per_pass.items()},
    )


def precision_recall_f1(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )
    return precision, recall, f1


def aggregate(cases: list[CaseScore]) -> dict:
    """Roll case scores up into overall + per-pass metrics."""
    tp = sum(c.tp for c in cases)
    fp = sum(c.fp for c in cases)
    fn = sum(c.fn for c in cases)
    precision, recall, f1 = precision_recall_f1(tp, fp, fn)

    per_pass_totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {"tp": 0, "fp": 0, "fn": 0}
    )
    for c in cases:
        for pass_name, b in c.per_pass.items():
            for k in ("tp", "fp", "fn"):
                per_pass_totals[pass_name][k] += b[k]

    per_pass = {}
    for pass_name, b in per_pass_totals.items():
        p, r, f = precision_recall_f1(b["tp"], b["fp"], b["fn"])
        per_pass[pass_name] = {**b, "precision": p, "recall": r, "f1": f}

    latencies = [c.latency_ms for c in cases]
    return {
        "num_cases": len(cases),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "avg_latency_ms": sum(latencies) / len(latencies) if latencies else 0.0,
        "per_pass": per_pass,
    }
