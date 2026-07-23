"""Style / convention review pass."""

from __future__ import annotations

from app.review.passes.base import BasePass
from app.review.schema import PassType


class StylePass(BasePass):
    name = "style"
    pass_type = PassType.style
    system_prompt = (
        "You are a code reviewer focused on readability and convention. Look "
        "for: unclear or misleading names, dead or duplicated code, overly "
        "complex functions, missing or misleading comments where they matter, "
        "inconsistent formatting relative to surrounding code, and violations "
        "of common language idioms. Keep these findings low severity (info or "
        "low) unless the style problem is likely to cause a real defect. Do "
        "not report correctness or security issues here."
    )
