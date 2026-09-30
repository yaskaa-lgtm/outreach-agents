"""Chooses the LLM implementation: deterministic fake in demo mode, Anthropic otherwise."""

from __future__ import annotations

from app.core.config import Settings
from app.core.errors import LLMNotConfiguredError
from app.providers.llm.anthropic_client import AnthropicLLMClient
from app.providers.llm.base import LLMClient


def build_llm_client(settings: Settings) -> LLMClient:
    if settings.demo_mode:
        from app.demo.llm_scripts import build_demo_llm

        return build_demo_llm()
    missing = settings.missing_llm_settings()
    if missing:
        raise LLMNotConfiguredError(
            "The LLM is not configured. Set these variables in .env: " + ", ".join(missing),
            missing=missing,
        )
    return AnthropicLLMClient(settings)
