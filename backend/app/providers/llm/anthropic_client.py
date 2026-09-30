"""Anthropic implementation of `LLMClient` (official `anthropic` SDK).

References (checked 2026-09-30):
- Messages API, structured outputs (`output_config.format`), strict tools, effort:
  https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- The SDK retries connection errors, 408, 409, 429 and 5xx with exponential backoff
  (`max_retries`): https://github.com/anthropics/anthropic-sdk-python#retries
"""

from __future__ import annotations

from typing import Any

import anthropic

from app.core.config import Settings
from app.providers.llm.base import (
    LLMProviderError,
    LLMRequest,
    LLMResponse,
    ModelRole,
    TokenUsage,
    ToolCall,
)


class AnthropicLLMClient:
    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        if client is None:
            if settings.anthropic_api_key is None:
                raise LLMProviderError("ANTHROPIC_API_KEY is not set")
            client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key.get_secret_value(),
                max_retries=3,
                timeout=300.0,
            )
        self._client = client
        self._models: dict[ModelRole, str | None] = {
            ModelRole.REASONING: settings.llm_model_reasoning,
            ModelRole.FAST: settings.llm_model_fast,
        }
        # Effort is only sent for the reasoning role: not every model supports it.
        self._effort: dict[ModelRole, str | None] = {
            ModelRole.REASONING: settings.llm_effort_reasoning,
            ModelRole.FAST: None,
        }

    def model_for(self, role: ModelRole) -> str:
        model = self._models[role]
        if not model:
            raise LLMProviderError(f"No model configured for role '{role}'")
        return model

    async def complete(self, request: LLMRequest) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self.model_for(request.role),
            "max_tokens": request.max_tokens,
            "system": request.system,
            "messages": request.messages,
        }
        if request.tools:
            kwargs["tools"] = [tool.to_api() for tool in request.tools]
        output_config: dict[str, Any] = {}
        if request.output_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": request.output_schema}
        effort = self._effort[request.role]
        if effort:
            output_config["effort"] = effort
        if output_config:
            kwargs["output_config"] = output_config

        try:
            message = await self._client.messages.create(**kwargs)
        except anthropic.APIError as exc:
            # The exception type only: messages may echo request content.
            raise LLMProviderError(type(exc).__name__) from exc

        text = "".join(block.text for block in message.content if block.type == "text")
        tool_calls = [
            ToolCall(id=block.id, name=block.name, input=dict(block.input))
            for block in message.content
            if block.type == "tool_use"
        ]
        usage = message.usage
        return LLMResponse(
            model=message.model,
            text=text,
            tool_calls=tool_calls,
            stop_reason=message.stop_reason,
            usage=TokenUsage(
                input_tokens=usage.input_tokens or 0,
                output_tokens=usage.output_tokens or 0,
                cache_read_input_tokens=usage.cache_read_input_tokens or 0,
                cache_creation_input_tokens=usage.cache_creation_input_tokens or 0,
            ),
            assistant_content=[block.to_dict() for block in message.content],
        )
