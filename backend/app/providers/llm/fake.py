"""Deterministic fake LLM for tests and demo mode: no network, no API key, no cost.

Each agent gets a `Script`: an ordered list of responses. The response returned depends
only on how many assistant turns the request already contains, so a given conversation
always produces the same answer.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from pydantic import BaseModel

from app.providers.llm.base import (
    LLMProviderError,
    LLMRequest,
    LLMResponse,
    TokenUsage,
    ToolCall,
)

FAKE_MODEL = "fake-llm"

Responder = Callable[[LLMRequest], LLMResponse]


def final_answer(payload: BaseModel | dict[str, Any] | str) -> LLMResponse:
    if isinstance(payload, BaseModel):
        text = payload.model_dump_json()
    elif isinstance(payload, dict):
        text = json.dumps(payload, ensure_ascii=False)
    else:
        text = payload
    return LLMResponse(
        model=FAKE_MODEL,
        text=text,
        tool_calls=[],
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=100, output_tokens=100),
        assistant_content=[{"type": "text", "text": text}],
    )


def tool_use(name: str, tool_input: dict[str, Any], call_id: str = "toolu_fake_1") -> LLMResponse:
    return LLMResponse(
        model=FAKE_MODEL,
        text="",
        tool_calls=[ToolCall(id=call_id, name=name, input=tool_input)],
        stop_reason="tool_use",
        usage=TokenUsage(input_tokens=100, output_tokens=20),
        assistant_content=[{"type": "tool_use", "id": call_id, "name": name, "input": tool_input}],
    )


def stop(stop_reason: str) -> LLMResponse:
    """A response that ends abnormally (e.g. 'refusal', 'max_tokens')."""
    return LLMResponse(
        model=FAKE_MODEL,
        text="",
        tool_calls=[],
        stop_reason=stop_reason,
        usage=TokenUsage(input_tokens=100, output_tokens=0),
        assistant_content=[],
    )


class Script:
    """Returns responses in order; the last one repeats if the conversation goes longer."""

    def __init__(self, responses: Sequence[LLMResponse]) -> None:
        if not responses:
            raise ValueError("A script needs at least one response")
        self.responses = list(responses)

    def __call__(self, request: LLMRequest) -> LLMResponse:
        turn = sum(1 for message in request.messages if message.get("role") == "assistant")
        return self.responses[min(turn, len(self.responses) - 1)]


class FakeLLM:
    def __init__(self, responders: Mapping[str, Responder]) -> None:
        self._responders = dict(responders)
        self.requests: list[LLMRequest] = []

    async def complete(self, request: LLMRequest) -> LLMResponse:
        self.requests.append(request)
        responder = self._responders.get(request.agent)
        if responder is None:
            raise LLMProviderError(f"FakeLLM has no script for agent '{request.agent}'")
        return responder(request)
