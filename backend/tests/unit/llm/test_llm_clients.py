from __future__ import annotations

from collections.abc import Callable
from typing import Any

import anthropic
import httpx2
import pytest
from anthropic.types import Message

from app.core.config import Settings
from app.providers.llm.anthropic_client import AnthropicLLMClient
from app.providers.llm.base import LLMProviderError, LLMRequest, ModelRole, ToolDefinition
from app.providers.llm.fake import FakeLLM, Script, final_answer, tool_use


def _request(**overrides: Any) -> LLMRequest:
    values: dict[str, Any] = {
        "agent": "tester",
        "prompt_version": "tester@abc",
        "role": ModelRole.REASONING,
        "system": "You are a test.",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 1000,
    }
    values.update(overrides)
    return LLMRequest(**values)


async def test_fake_llm_follows_its_script_turn_by_turn() -> None:
    llm = FakeLLM(
        {
            "tester": Script(
                [tool_use("fetch_page", {"url": "https://example.com/"}), final_answer("{}")]
            )
        }
    )
    first = await llm.complete(_request())
    second = await llm.complete(
        _request(messages=[{"role": "user", "content": "hi"}, {"role": "assistant", "content": []}])
    )
    assert first.tool_calls[0].name == "fetch_page"
    assert second.text == "{}"
    assert len(llm.requests) == 2


async def test_fake_llm_without_script_fails_loudly() -> None:
    with pytest.raises(LLMProviderError):
        await FakeLLM({}).complete(_request())


class StubMessages:
    def __init__(self, result: Message | Exception) -> None:
        self.result = result
        self.kwargs: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> Message:
        self.kwargs = kwargs
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class StubAnthropic:
    def __init__(self, result: Message | Exception) -> None:
        self.messages = StubMessages(result)


def _message(content: list[dict[str, Any]], stop_reason: str = "end_turn") -> Message:
    return Message.model_validate(
        {
            "id": "msg_test",
            "type": "message",
            "role": "assistant",
            "model": "model-under-test",
            "content": content,
            "stop_reason": stop_reason,
            "stop_sequence": None,
            "usage": {"input_tokens": 1200, "output_tokens": 300, "cache_read_input_tokens": 50},
        }
    )


@pytest.fixture
def llm_settings(make_settings: Callable[..., Settings]) -> Settings:
    return make_settings(
        demo_mode=False,
        llm_model_reasoning="model-reasoning-from-env",
        llm_model_fast="model-fast-from-env",
        llm_effort_reasoning="medium",
    )


async def test_anthropic_client_builds_the_request_from_configuration(
    llm_settings: Settings,
) -> None:
    stub = StubAnthropic(_message([{"type": "text", "text": '{"ok": true}'}]))
    client = AnthropicLLMClient(llm_settings, client=stub)
    tool = ToolDefinition("fetch_page", "Read a page.", {"type": "object", "properties": {}})

    response = await client.complete(_request(tools=[tool], output_schema={"type": "object"}))

    sent = stub.messages.kwargs
    assert sent["model"] == "model-reasoning-from-env"
    assert sent["tools"][0]["strict"] is True
    assert sent["output_config"] == {
        "format": {"type": "json_schema", "schema": {"type": "object"}},
        "effort": "medium",
    }
    assert response.text == '{"ok": true}'
    assert response.usage.input_tokens == 1200
    assert response.usage.cache_read_input_tokens == 50


async def test_fast_role_uses_fast_model_without_effort(llm_settings: Settings) -> None:
    stub = StubAnthropic(_message([{"type": "text", "text": "fine"}]))
    await AnthropicLLMClient(llm_settings, client=stub).complete(_request(role=ModelRole.FAST))
    assert stub.messages.kwargs["model"] == "model-fast-from-env"
    assert "output_config" not in stub.messages.kwargs


async def test_tool_calls_are_parsed(llm_settings: Settings) -> None:
    stub = StubAnthropic(
        _message(
            [
                {
                    "type": "tool_use",
                    "id": "toolu_1",
                    "name": "fetch_page",
                    "input": {"url": "https://example.com/"},
                }
            ],
            stop_reason="tool_use",
        )
    )
    response = await AnthropicLLMClient(llm_settings, client=stub).complete(_request())
    assert response.tool_calls[0].input == {"url": "https://example.com/"}
    assert response.assistant_content[0]["type"] == "tool_use"


async def test_provider_errors_are_wrapped_without_details(llm_settings: Settings) -> None:
    error = anthropic.APIConnectionError(
        request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    )
    stub = StubAnthropic(error)
    with pytest.raises(LLMProviderError, match="APIConnectionError"):
        await AnthropicLLMClient(llm_settings, client=stub).complete(_request())


def test_missing_model_is_reported(make_settings: Callable[..., Settings]) -> None:
    client = AnthropicLLMClient(
        make_settings(demo_mode=False), client=StubAnthropic(RuntimeError())
    )
    with pytest.raises(LLMProviderError, match="No model configured"):
        client.model_for(ModelRole.REASONING)
