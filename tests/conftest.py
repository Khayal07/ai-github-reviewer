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
