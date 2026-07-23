"""Application settings loaded from environment / .env."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration, populated from environment variables / `.env`."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- General ---------------------------------------------------------
    app_env: str = "development"
    log_level: str = "INFO"

    # --- Database --------------------------------------------------------
    database_url: str = "sqlite:///./ai_reviewer.db"

    # --- LLM -------------------------------------------------------------
    llm_provider: str = "openai"  # openai | anthropic
    llm_model: str = "gpt-4o"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None

    # --- GitHub App ------------------------------------------------------
    github_app_id: str | None = None
    github_webhook_secret: str | None = None
    github_app_private_key: str | None = None
    github_app_private_key_path: str | None = None

    # --- GitHub token (Action / manual runs) -----------------------------
    github_token: str | None = None

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def resolve_app_private_key(self) -> str | None:
        """Return the GitHub App private key PEM from inline value or file path."""
        if self.github_app_private_key:
            # Allow escaped newlines when supplied inline via env.
            return self.github_app_private_key.replace("\\n", "\n")
        if self.github_app_private_key_path:
            path = Path(self.github_app_private_key_path)
            if path.exists():
                return path.read_text(encoding="utf-8")
        return None


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
