"""Unit tests for mapping findings to GitHub review comments."""

from app.github.comments import (
    build_summary,
    finding_to_comment,
    map_findings,
    verdict_to_event,
)
from app.github.diff import parse_files
from app.review.schema import (
    Finding,
    PassType,
    ReviewResult,
    Severity,
    Verdict,
    compute_counts,
)

# new-file lines 1,2,3,4 are commentable (see test_diff_parser SINGLE case)
PATCH = """@@ -1,3 +1,4 @@
 line1
-line2
+line2new
+line3added
 line4"""

DIFF = parse_files([{"filename": "app.py", "status": "modified", "patch": PATCH}])


def _finding(**kw):
    base = dict(
        file="app.py", line=3, severity=Severity.high,
        pass_type=PassType.correctness, title="Bug", message="Boom",
    )
    base.update(kw)
    return Finding(**base)


def test_commentable_finding_maps_to_payload():
    payload = finding_to_comment(_finding(line=3), DIFF)
    assert payload == {
        "path": "app.py",
        "body": payload["body"],  # checked separately
        "line": 3,
        "side": "RIGHT",
    }
    assert "Bug" in payload["body"] and "Boom" in payload["body"]


def test_out_of_diff_line_is_skipped():
    assert finding_to_comment(_finding(line=999), DIFF) is None


def test_finding_on_unknown_file_is_skipped():
    assert finding_to_comment(_finding(file="missing.py", line=3), DIFF) is None


def test_single_line_suggestion_becomes_suggestion_block():
    payload = finding_to_comment(_finding(line=3, suggestion="return x"), DIFF)
    assert "```suggestion" in payload["body"]
    assert "return x" in payload["body"]


def test_multiline_finding_sets_start_line():
    payload = finding_to_comment(_finding(line=1, end_line=3), DIFF)
    assert payload["start_line"] == 1
    assert payload["line"] == 3
    assert payload["start_side"] == "RIGHT"
    # Multi-line comments do not emit an applicable suggestion block.
    payload2 = finding_to_comment(_finding(line=1, end_line=3, suggestion="x"), DIFF)
    assert "```suggestion" not in payload2["body"]


def test_map_findings_splits_inline_and_skipped():
    findings = [_finding(line=3), _finding(line=999), _finding(file="ghost.py", line=1)]
    inline, skipped = map_findings(findings, DIFF)
    assert len(inline) == 1
    assert len(skipped) == 2


def test_verdict_to_event():
    assert verdict_to_event(Verdict.approve) == "APPROVE"
    assert verdict_to_event(Verdict.comment) == "COMMENT"
    assert verdict_to_event(Verdict.request_changes) == "REQUEST_CHANGES"


def test_build_summary_includes_counts_and_skipped():
    findings = [_finding(line=3, severity=Severity.high)]
    result = ReviewResult(
        findings=findings,
        verdict=Verdict.request_changes,
        counts=compute_counts(findings),
    )
    skipped = [_finding(file="ghost.py", line=1, title="Ghost", message="hidden")]
    summary = build_summary(result, skipped)
    assert "Changes requested" in summary
    assert "high" in summary
    assert "Ghost" in summary  # skipped findings are surfaced
    assert "ghost.py:1" in summary


def test_build_summary_clean_review():
    result = ReviewResult(findings=[], verdict=Verdict.approve, counts=compute_counts([]))
    summary = build_summary(result, [])
    assert "Approved" in summary
    assert "**0** finding" in summary
