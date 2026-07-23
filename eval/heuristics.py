"""A dependency-free heuristic reviewer used as the offline eval baseline.

It implements the same `LLMClient` interface as the real providers, so the
eval harness measures a genuine detector without needing API keys. It scans the
added lines in the rendered diff for well-known bug/security patterns. Swap in
an OpenAI/Anthropic client via `run_eval.py --provider` to score the real model.
"""

from __future__ import annotations

import re

from app.review.llm import LLMClient
from app.review.schema import Finding, PassType, Severity

_FILE_RE = re.compile(r"^### FILE: (.+?) \(status:")
_ADDED_RE = re.compile(r"^\s*(\d+)\+ ?(.*)$")

# (compiled pattern, severity, title)
_SECURITY_RULES = [
    (re.compile(r"\beval\s*\("), Severity.critical, "Use of eval()"),
    (re.compile(r"\bexec\s*\("), Severity.critical, "Use of exec()"),
    (
        re.compile(r"(?i)\b(password|passwd|secret|token|api_key)\b\s*=\s*['\"]"),
        Severity.high,
        "Hardcoded secret",
    ),
    (
        re.compile(r"(?i)(select|insert|update|delete)\b.*['\"]\s*\+|\+\s*.*['\"].*(where|values)"),
        Severity.high,
        "Possible SQL injection (string concatenation)",
    ),
    (re.compile(r"\bpickle\.loads\s*\("), Severity.high, "Unsafe deserialization"),
    (re.compile(r"shell\s*=\s*True"), Severity.high, "subprocess with shell=True"),
    (re.compile(r"\bmd5\s*\(|hashlib\.md5"), Severity.medium, "Weak hash (MD5)"),
]

_CORRECTNESS_RULES = [
    (re.compile(r"[!=]=\s*None\b"), Severity.medium, "Compare to None with is/is not"),
    (re.compile(r"^\s*except\s*:\s*$"), Severity.medium, "Bare except clause"),
    (re.compile(r"\bassert\s+.+,"), Severity.low, "assert used for runtime validation"),
]


def _scan(added: list[tuple[str, int, str]], pass_type: PassType, rules) -> list[Finding]:
    findings: list[Finding] = []
    for file, line, content in added:
        for pattern, severity, title in rules:
            if pattern.search(content):
                findings.append(
                    Finding(
                        file=file,
                        line=line,
                        severity=severity,
                        pass_type=pass_type,
                        title=title,
                        message=f"{title} on this line.",
                        confidence=0.9,
                    )
                )
                break  # one finding per line per pass
    return findings


class HeuristicClient(LLMClient):
    async def review(
        self, *, system: str, user: str, pass_type: PassType
    ) -> list[Finding]:
        added: list[tuple[str, int, str]] = []
        current_file = ""
        for raw in user.split("\n"):
            fm = _FILE_RE.match(raw)
            if fm:
                current_file = fm.group(1)
                continue
            am = _ADDED_RE.match(raw)
            if am and current_file:
                added.append((current_file, int(am.group(1)), am.group(2)))

        if pass_type == PassType.security:
            return _scan(added, pass_type, _SECURITY_RULES)
        if pass_type == PassType.correctness:
            return _scan(added, pass_type, _CORRECTNESS_RULES)
        return []
