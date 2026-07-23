"""Parsing and validation for the per-repo `.ai-reviewer.yml` file.

Every field is optional; a missing or malformed file yields sensible defaults
so the reviewer never hard-fails on a bad config.
"""

from __future__ import annotations

import logging
import re

import yaml
from pydantic import BaseModel, Field, ValidationError

from app.review.schema import Severity

logger = logging.getLogger("ai_reviewer.config")

_DEFAULT_IGNORES = [
    "**/*.lock",
    "**/*.min.js",
    "dist/**",
    "build/**",
    "vendor/**",
    "node_modules/**",
]


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Translate a gitignore-style glob to a regex.

    `**` matches across directory separators, `*` matches within a path
    segment, `?` matches a single non-separator character.
    """
    out: list[str] = []
    i = 0
    while i < len(pattern):
        if pattern[i] == "*":
            if pattern[i : i + 2] == "**":
                out.append(".*")
                i += 2
                if i < len(pattern) and pattern[i] == "/":
                    i += 1  # `**/` also matches zero directories
            else:
                out.append("[^/]*")
                i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


class LLMOverride(BaseModel):
    provider: str | None = None
    model: str | None = None


class ReviewerConfig(BaseModel):
    passes: dict[str, bool] = Field(
        default_factory=lambda: {
            "correctness": True,
            "security": True,
            "style": True,
            "tests": True,
        }
    )
    block_severity: Severity = Severity.high
    min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    ignore_paths: list[str] = Field(default_factory=lambda: list(_DEFAULT_IGNORES))
    max_files: int = Field(default=50, ge=1)
    llm: LLMOverride = Field(default_factory=LLMOverride)

    def is_ignored(self, path: str) -> bool:
        """True if `path` matches any ignore pattern."""
        norm = path.replace("\\", "/")
        base = norm.rsplit("/", 1)[-1]
        for pattern in self.ignore_paths:
            rx = _glob_to_regex(pattern)
            if rx.match(norm):
                return True
            # A pattern with no separator also matches the basename anywhere.
            if "/" not in pattern and rx.match(base):
                return True
        return False

    @classmethod
    def load(cls, text: str | None) -> ReviewerConfig:
        """Parse YAML config text, falling back to defaults on any problem."""
        if not text or not text.strip():
            return cls()
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            logger.warning("Invalid .ai-reviewer.yml (YAML error): %s", exc)
            return cls()
        if not isinstance(data, dict):
            logger.warning("Invalid .ai-reviewer.yml: expected a mapping.")
            return cls()
        try:
            return cls.model_validate(data)
        except ValidationError as exc:
            logger.warning("Invalid .ai-reviewer.yml (schema error): %s", exc)
            return cls()
