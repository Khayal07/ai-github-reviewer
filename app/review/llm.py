"""Provider-agnostic LLM client for producing structured review findings.

`LLMClient` is the interface the review passes depend on. Two implementations
ship out of the box — OpenAI (default) and Anthropic — selected by config. A
pass hands the client a system prompt + rendered diff and gets back a list of
`Finding` objects, parsed and validated from the model's structured output.
"""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from app.review.schema import Finding, PassType, Severity

# JSON schema the models are asked to fill. Kept intentionally permissive:
# pass_type and side are injected by us, not trusted from the model.
FINDINGS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "line": {"type": "integer"},
                    "end_line": {"type": ["integer", "null"]},
                    "severity": {
                        "type": "string",
                        "enum": [s.value for s in Severity],
                    },
                    "title": {"type": "string"},
                    "message": {"type": "string"},
                    "suggestion": {"type": ["string", "null"]},
                    "confidence": {"type": "number"},
                },
                "required": ["file", "line", "severity", "title", "message"],
            },
        }
    },
    "required": ["findings"],
}


def parse_findings(data: dict | None, pass_type: PassType) -> list[Finding]:
    """Robustly parse a model payload into validated `Finding` objects.

    Skips malformed entries rather than raising, so one bad finding never
    sinks an entire pass.
    """
    if not isinstance(data, dict):
        return []
    out: list[Finding] = []
    for item in data.get("findings", []) or []:
        if not isinstance(item, dict):
            continue
        file = item.get("file") or item.get("path")
        line = item.get("line")
        if not file or line is None:
            continue
        try:
            line = int(line)
        except (TypeError, ValueError):
            continue
        try:
            severity = Severity(str(item.get("severity", "medium")).lower())
        except ValueError:
            severity = Severity.medium
        side = str(item.get("side", "RIGHT")).upper()
        if side not in ("RIGHT", "LEFT"):
            side = "RIGHT"
        try:
            confidence = float(item.get("confidence", 0.8))
        except (TypeError, ValueError):
            confidence = 0.8
        confidence = min(max(confidence, 0.0), 1.0)
        end_line = item.get("end_line")
        try:
            end_line = int(end_line) if end_line is not None else None
        except (TypeError, ValueError):
            end_line = None
        out.append(
            Finding(
                file=str(file),
                line=line,
                end_line=end_line,
                side=side,
                severity=severity,
                pass_type=pass_type,
                title=str(item.get("title") or "Issue")[:255],
                message=str(item.get("message", "")),
                suggestion=item.get("suggestion") or None,
                confidence=confidence,
            )
        )
    return out


class LLMClient(ABC):
    """Interface every review pass depends on."""

    @abstractmethod
    async def review(
        self, *, system: str, user: str, pass_type: PassType
    ) -> list[Finding]:
        """Run one review pass and return structured findings."""


class OpenAIClient(LLMClient):
    """Default client using OpenAI chat completions with JSON output."""

    def __init__(self, model: str, api_key: str) -> None:
        from openai import AsyncOpenAI

        self.model = model
        self._client = AsyncOpenAI(api_key=api_key)

    async def review(
        self, *, system: str, user: str, pass_type: PassType
    ) -> list[Finding]:
        resp = await self._client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        content = resp.choices[0].message.content or "{}"
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            return []
        return parse_findings(data, pass_type)


class AnthropicClient(LLMClient):
    """Client using the Anthropic Messages API with forced tool use for
    reliable structured output. Defaults to Claude Opus 4.8."""

    _TOOL_NAME = "report_findings"

    def __init__(self, model: str, api_key: str) -> None:
        from anthropic import AsyncAnthropic

        self.model = model
        self._client = AsyncAnthropic(api_key=api_key)

    async def review(
        self, *, system: str, user: str, pass_type: PassType
    ) -> list[Finding]:
        resp = await self._client.messages.create(
            model=self.model,
            max_tokens=8000,
            system=system,
            messages=[{"role": "user", "content": user}],
            tools=[
                {
                    "name": self._TOOL_NAME,
                    "description": "Report the review findings for this diff.",
                    "input_schema": FINDINGS_SCHEMA,
                }
            ],
            tool_choice={"type": "tool", "name": self._TOOL_NAME},
        )
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                return parse_findings(block.input, pass_type)
        return []


def build_llm_client(
    provider: str,
    model: str,
    *,
    openai_api_key: str | None = None,
    anthropic_api_key: str | None = None,
) -> LLMClient:
    """Construct the configured LLM client, raising if its key is missing."""
    provider = provider.lower()
    if provider == "openai":
        if not openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for the OpenAI provider.")
        return OpenAIClient(model=model or "gpt-4o", api_key=openai_api_key)
    if provider == "anthropic":
        if not anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required for the Anthropic provider."
            )
        return AnthropicClient(
            model=model or "claude-opus-4-8", api_key=anthropic_api_key
        )
    raise ValueError(f"Unknown LLM provider: {provider!r}")
