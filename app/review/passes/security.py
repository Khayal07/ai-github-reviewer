"""Security review pass."""

from __future__ import annotations

from app.review.passes.base import BasePass
from app.review.schema import PassType


class SecurityPass(BasePass):
    name = "security"
    pass_type = PassType.security
    system_prompt = (
        "You are an application security engineer reviewing a diff for "
        "vulnerabilities. Look for: injection (SQL, command, path, template), "
        "hardcoded secrets or credentials, missing authentication or "
        "authorization checks, unsafe deserialization, SSRF, path traversal, "
        "weak cryptography, insecure randomness, and unvalidated user input "
        "reaching a sensitive sink. Rate exploitable issues high or critical. "
        "Only report security-relevant findings."
    )
