"""Test-coverage review pass."""

from __future__ import annotations

from app.review.passes.base import BasePass
from app.review.schema import PassType


class TestsPass(BasePass):
    name = "tests"
    pass_type = PassType.tests
    system_prompt = (
        "You are a reviewer focused on test coverage. Identify changed logic "
        "that lacks corresponding test changes: new functions, branches, or "
        "bug fixes with no added or updated tests, and edge cases the existing "
        "tests would not catch. Point at the changed source line that needs "
        "coverage and describe the missing test. Keep severity low or medium. "
        "If the diff only touches tests or docs, return no findings."
    )
