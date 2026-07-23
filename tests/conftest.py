"""Shared pytest fixtures and test environment setup.

Runs before any application module is imported so the app binds to an
isolated SQLite database and never touches real credentials.
"""

from __future__ import annotations

import os

os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_ai_reviewer.db")
os.environ.setdefault("LLM_PROVIDER", "openai")
os.environ.setdefault("OPENAI_API_KEY", "test-key")

# Keep the suite hermetic: never inherit real GitHub credentials from a local
# .env (a set webhook secret would make the webhook demand a signature the
# tests don't send). Empty values override the .env file.
for _var in (
    "GITHUB_WEBHOOK_SECRET",
    "GITHUB_APP_ID",
    "GITHUB_APP_PRIVATE_KEY",
    "GITHUB_APP_PRIVATE_KEY_PATH",
    "GITHUB_TOKEN",
    "ANTHROPIC_API_KEY",
):
    os.environ.setdefault(_var, "")
