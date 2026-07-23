"""Unit tests for eval scoring and the heuristic detector."""

import pytest

from app.review.schema import Finding, PassType, Severity
from eval.heuristics import HeuristicClient
from eval.metrics import aggregate, precision_recall_f1, score_case


def _f(file="a.py", line=1, pass_type=PassType.security):
    return Finding(
        file=file, line=line, severity=Severity.high, pass_type=pass_type,
        title="t", message="m",
    )


def test_precision_recall_f1():
    p, r, f = precision_recall_f1(tp=3, fp=1, fn=1)
    assert p == 0.75
    assert r == 0.75
    assert f == pytest.approx(0.75)
    assert precision_recall_f1(0, 0, 0) == (0.0, 0.0, 0.0)


def test_score_case_matches_within_tolerance():
    produced = [_f(line=3), _f(line=50)]  # one match (±2), one false positive
    gt = [{"file": "a.py", "line": 2, "pass_type": "security"}]
    score = score_case("c", produced, gt, latency_ms=1.0)
    assert score.tp == 1
    assert score.fp == 1
    assert score.fn == 0


def test_score_case_pass_type_must_match():
    produced = [_f(line=2, pass_type=PassType.style)]
    gt = [{"file": "a.py", "line": 2, "pass_type": "security"}]
    score = score_case("c", produced, gt, latency_ms=1.0)
    assert score.tp == 0 and score.fn == 1 and score.fp == 1


def test_clean_case_counts_findings_as_false_positives():
    score = score_case("clean", [_f()], [], latency_ms=1.0)
    assert score.fp == 1 and score.tp == 0 and score.fn == 0


def test_aggregate_rolls_up():
    scores = [
        score_case("a", [_f(line=2)], [{"file": "a.py", "line": 2, "pass_type": "security"}], 5.0),
        score_case("b", [], [{"file": "b.py", "line": 1, "pass_type": "security"}], 3.0),
    ]
    summary = aggregate(scores)
    assert summary["tp"] == 1 and summary["fn"] == 1
    assert summary["recall"] == 0.5
    assert summary["avg_latency_ms"] == 4.0


@pytest.mark.asyncio
async def test_heuristic_detects_eval_and_secret():
    client = HeuristicClient()
    rendered = (
        "### FILE: app/auth.py (status: modified)\n"
        "     3+ PASSWORD = \"hunter2\"\n"
        "     4+ TOKEN = eval(input())\n"
    )
    findings = await client.review(system="", user=rendered, pass_type=PassType.security)
    lines = {f.line for f in findings}
    assert lines == {3, 4}


@pytest.mark.asyncio
async def test_heuristic_detects_none_compare():
    client = HeuristicClient()
    rendered = "### FILE: u.py (status: modified)\n     2+     if x == None:\n"
    findings = await client.review(system="", user=rendered, pass_type=PassType.correctness)
    assert len(findings) == 1 and findings[0].line == 2
