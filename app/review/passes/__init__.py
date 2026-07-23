"""Focused review passes and a factory to build the enabled set."""

from __future__ import annotations

from app.review.passes.base import BasePass
from app.review.passes.correctness import CorrectnessPass
from app.review.passes.security import SecurityPass
from app.review.passes.style import StylePass
from app.review.passes.tests import TestsPass

_PASS_REGISTRY: dict[str, type[BasePass]] = {
    "correctness": CorrectnessPass,
    "security": SecurityPass,
    "style": StylePass,
    "tests": TestsPass,
}


def build_passes(enabled: dict[str, bool]) -> list[BasePass]:
    """Instantiate the passes whose config toggle is truthy."""
    return [cls() for name, cls in _PASS_REGISTRY.items() if enabled.get(name, True)]


__all__ = [
    "BasePass",
    "CorrectnessPass",
    "SecurityPass",
    "StylePass",
    "TestsPass",
    "build_passes",
]
