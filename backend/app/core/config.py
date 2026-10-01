"""Application settings, loaded from environment variables (and `.env` in development).

Every secret is a `SecretStr`, so it never shows up in logs, reprs or tracebacks.
Defaults are the *safe* ones: demo mode on, dry run on.
"""

from __future__ import annotations

from enum import StrEnum
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
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

    # --- Authentication (single admin account in the MVP) ---------------------
    admin_email: str | None = None
    admin_password: SecretStr | None = None
    session_cookie_name: str = "oa_session"
    session_cookie_secure: bool = True
    session_ttl_hours: int = Field(default=12, gt=0, le=24 * 30)
    login_max_failures: int = Field(default=5, gt=0)
    login_lockout_minutes: int = Field(default=15, gt=0)
    api_rate_limit_per_minute: int = Field(default=300, gt=0)

    # --- LLM ----------------------------------------------------------------------
    # Model names are never hard-coded: they come from the environment only.
    anthropic_api_key: SecretStr | None = None
    llm_model_reasoning: str | None = None
    llm_model_fast: str | None = None
    # Depth of reasoning for the reasoning model (empty = API default).
    llm_effort_reasoning: Literal["low", "medium", "high", "xhigh", "max"] | None = None
    llm_max_output_tokens: int = Field(default=16000, gt=0)
    # Prices in USD per million tokens, per model role (copied from the official pricing
    # page into `.env`, so that changing the model never silently breaks cost tracking).
    llm_price_reasoning_input_usd_per_mtok: float | None = Field(default=None, ge=0)
    llm_price_reasoning_output_usd_per_mtok: float | None = Field(default=None, ge=0)
    llm_price_fast_input_usd_per_mtok: float | None = Field(default=None, ge=0)
    llm_price_fast_output_usd_per_mtok: float | None = Field(default=None, ge=0)
    usd_to_eur_rate: float | None = Field(default=None, gt=0)
    # Initial daily budget of a new workspace; the live value is editable in the app.
    daily_llm_budget_eur: float = Field(default=2.0, gt=0)

    # --- Web fetching (polite, SSRF-safe bot) ----------------------------------------
    bot_user_agent: str = (
        "outreach-agents-bot/0.1 (+https://github.com/yaskaa-lgtm/outreach-agents)"
    )
    # Name matched against robots.txt "User-agent" lines (RFC 9309 product token).
    bot_robots_name: str = "outreach-agents-bot"
    fetch_timeout_seconds: float = Field(default=15.0, gt=0)
    fetch_max_bytes: int = Field(default=2_000_000, gt=0)
    fetch_max_redirects: int = Field(default=3, ge=0)
    fetch_min_interval_per_host_seconds: float = Field(default=1.0, ge=0)
    offer_analysis_max_pages: int = Field(default=6, gt=0, le=20)

    # --- Discovery: companies and contacts (Phase 2) -------------------------
    hunter_api_key: SecretStr | None = None
    # Hunter's free plan has 50 credits a month; calls stop when this many were used.
    hunter_monthly_credit_limit: int = Field(default=50, ge=0)
    companies_per_segment: int = Field(default=10, gt=0)
    companies_per_segment_max: int = Field(default=50, gt=0)
    # recherche-entreprises.api.gouv.fr allows at most 7 requests/second per IP.
    registry_min_interval_seconds: float = Field(default=0.25, ge=0)
    # Pages read to find the SIREN on a company website (home + legal notice pages).
    domain_check_max_pages: int = Field(default=3, gt=0, le=10)

    # --- Encryption at rest (used from Phase 4: SMTP/IMAP credentials) -------
    fernet_key: SecretStr | None = None

    # --- Worker ---------------------------------------------------------------
    worker_poll_interval_seconds: float = Field(default=5.0, gt=0)

    @field_validator("hunter_api_key", mode="before")
    @classmethod
    def _empty_key_means_no_hunter(cls, value: object) -> object:
        return None if value == "" else value

    @property
    def mode(self) -> RunMode:
        """Demo mode wins over everything; otherwise DRY_RUN unless explicitly disabled."""
        if self.demo_mode:
            return RunMode.DEMO
        if self.dry_run:
            return RunMode.DRY_RUN
        return RunMode.LIVE

    def missing_llm_settings(self) -> list[str]:
        """Variables required to call the real LLM (empty list = ready, or demo mode)."""
        if self.demo_mode:
            return []
        required = {
            "ANTHROPIC_API_KEY": self.anthropic_api_key,
            "LLM_MODEL_REASONING": self.llm_model_reasoning,
            "LLM_MODEL_FAST": self.llm_model_fast,
            "LLM_PRICE_REASONING_INPUT_USD_PER_MTOK": self.llm_price_reasoning_input_usd_per_mtok,
            "LLM_PRICE_REASONING_OUTPUT_USD_PER_MTOK": self.llm_price_reasoning_output_usd_per_mtok,
            "LLM_PRICE_FAST_INPUT_USD_PER_MTOK": self.llm_price_fast_input_usd_per_mtok,
            "LLM_PRICE_FAST_OUTPUT_USD_PER_MTOK": self.llm_price_fast_output_usd_per_mtok,
            "USD_TO_EUR_RATE": self.usd_to_eur_rate,
        }
        return [name for name, value in required.items() if value is None]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings (cached: the environment is read once)."""
    return Settings()
