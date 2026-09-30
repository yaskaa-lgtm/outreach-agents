"""Application settings, loaded from environment variables (and `.env` in development).

Every secret is a `SecretStr`, so it never shows up in logs, reprs or tracebacks.
Defaults are the *safe* ones: demo mode on, dry run on.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class RunMode(StrEnum):
    """What the application is allowed to do with emails.

    - DEMO: fake LLM, fake data providers, emails captured by Mailpit. No API key needed.
    - DRY_RUN: real LLM and data providers, but every email is captured by Mailpit.
    - LIVE: emails really leave. Requires DRY_RUN=false *and* a confirmation in the UI.
    """

    DEMO = "DEMO"
    DRY_RUN = "DRY_RUN"
    LIVE = "LIVE"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        # `.env` also holds variables for docker compose (POSTGRES_*): ignore them here.
        extra="ignore",
        # An empty variable (e.g. `HUNTER_API_KEY=`) means "not set".
        env_ignore_empty=True,
    )

    # --- Runtime ------------------------------------------------------------
    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    demo_mode: bool = True
    dry_run: bool = True

    # --- Database -----------------------------------------------------------
    # Local development default; docker compose overrides it with the `db` host.
    # 127.0.0.1 rather than localhost: on Windows, localhost tries IPv6 first and the
    # refused connection is slow, while Docker publishes the port on IPv4 only.
    database_url: str = (
        "postgresql+psycopg://outreach:outreach_dev_password@127.0.0.1:5432/outreach"
    )

    # --- HTTP API -----------------------------------------------------------
    cors_allow_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    # --- Dry-run SMTP sink (Mailpit) -----------------------------------------
    mailpit_smtp_host: str = "127.0.0.1"
    mailpit_smtp_port: int = 1025

    # --- LLM (used from Phase 1) --------------------------------------------
    # Model names are never hard-coded: they come from the environment only.
    anthropic_api_key: SecretStr | None = None
    llm_model_reasoning: str | None = None
    llm_model_fast: str | None = None

    # --- Data providers (used from Phase 2) ---------------------------------
    hunter_api_key: SecretStr | None = None

    # --- Encryption at rest (used from Phase 1) ------------------------------
    fernet_key: SecretStr | None = None

    # --- Worker ---------------------------------------------------------------
    worker_poll_interval_seconds: float = Field(default=5.0, gt=0)

    @property
    def mode(self) -> RunMode:
        """Demo mode wins over everything; otherwise DRY_RUN unless explicitly disabled."""
        if self.demo_mode:
            return RunMode.DEMO
        if self.dry_run:
            return RunMode.DRY_RUN
        return RunMode.LIVE


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings (cached: the environment is read once)."""
    return Settings()
