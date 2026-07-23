"""Base class shared by all review passes."""

from __future__ import annotations

from abc import ABC

from app.review.llm import LLMClient
from app.review.schema import Finding, PassType

_SHARED_INSTRUCTIONS = """\
You are reviewing a GitHub pull request diff. Only report issues introduced or
affected by the changed lines (lines shown with a `+` marker or referenced by
the surrounding context). Cite the exact new-file line number shown in the
left gutter. Do not comment on unchanged code unless a change breaks it.

Return a JSON object matching this shape:
{"findings": [{"file": str, "line": int, "end_line": int|null,
  "severity": "info|low|medium|high|critical", "title": str, "message": str,
  "suggestion": str|null, "confidence": number 0..1}]}

Stay strictly within your assigned category (described in the system prompt).
If an issue belongs to a different category, do not report it here — another
pass covers it. Report each distinct issue exactly once, on its own line; do
not restate the same problem multiple times.

Report every issue in your category, including low-severity and uncertain ones,
with an honest confidence — a downstream filter handles ranking. If there are
no issues, return {"findings": []}. `line` must be a real line number from the
diff. Keep `message` concrete and actionable; put a concrete fix in
`suggestion` when you have one.
"""


class BasePass(ABC):
    """A single focused LLM review pass."""

    name: str
    pass_type: PassType
    system_prompt: str

    async def run(self, rendered_diff: str, llm: LLMClient) -> list[Finding]:
        user = f"{_SHARED_INSTRUCTIONS}\n\n=== DIFF ===\n{rendered_diff}"
        return await llm.review(
            system=self.system_prompt, user=user, pass_type=self.pass_type
        )
