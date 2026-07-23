"""Correctness / bug-finding pass."""

from __future__ import annotations

from app.review.passes.base import BasePass
from app.review.schema import PassType


class CorrectnessPass(BasePass):
    name = "correctness"
    pass_type = PassType.correctness
    system_prompt = (
        "You are a meticulous senior engineer reviewing code for correctness "
        "bugs. Look for: logic errors, off-by-one mistakes, null/None and "
        "undefined handling, incorrect error handling, resource leaks, race "
        "conditions, incorrect API or library usage, broken control flow, and "
        "edge cases the change fails to handle. Prefer high-signal findings "
        "that could cause wrong behavior, a crash, or a failing test. Do not "
        "report pure style or naming issues here."
    )
