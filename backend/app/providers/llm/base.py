"""Provider-neutral types for one LLM call.

Messages use the Anthropic content-block format as the internal representation; another
provider would convert it in its own adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class ModelRole(StrEnum):
    """Which configured model to use. The model name itself lives in `.env`."""

    REASONING = "reasoning"
    FAST = "fast"


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]

    def to_api(self) -> dict[str, Any]:
        # strict: the model's tool inputs always match the schema.
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "strict": True,
        }


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0


@dataclass(frozen=True)
class LLMRequest:
    agent: str
    prompt_version: str
    role: ModelRole
    system: str
    messages: list[dict[str, Any]]
    max_tokens: int
    tools: list[ToolDefinition] = field(default_factory=list)
    # JSON schema the final answer must follow (structured output), or None for free text.
    output_schema: dict[str, Any] | None = None


@dataclass(frozen=True)
class LLMResponse:
    model: str
    text: str
    tool_calls: list[ToolCall]
    stop_reason: str | None
    usage: TokenUsage
    # Assistant content blocks, sent back unchanged in the next request of the same run.
    assistant_content: list[dict[str, Any]]


class LLMProviderError(Exception):
    """The provider failed (network, 5xx after retries, invalid request...)."""


class LLMClient(Protocol):
    async def complete(self, request: LLMRequest) -> LLMResponse: ...
