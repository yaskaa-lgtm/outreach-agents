from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, Field

from app.agents.runtime import Prompt, ToolFailure, load_prompt, run_structured_agent
from app.core.errors import AgentError
from app.providers.llm.base import ModelRole, ToolDefinition
from app.providers.llm.fake import FakeLLM, Script, final_answer, stop, tool_use


class Answer(BaseModel):
    city: str
    score: int = Field(ge=0, le=10)


PROMPT = Prompt(name="tester", text="Answer with JSON.")
LOOKUP = ToolDefinition("lookup", "Look something up.", {"type": "object", "properties": {}})


async def _run(
    llm: FakeLLM, tools: dict[str, Any] | None = None, max_tool_calls: int = 3
) -> Answer:
    return await run_structured_agent(
        llm=llm,
        agent="tester",
        prompt=PROMPT,
        role=ModelRole.FAST,
        user_content="Where?",
        output_model=Answer,
        max_tokens=500,
        tools=tools,
        max_tool_calls=max_tool_calls,
    )


def _last_tool_results(llm: FakeLLM) -> list[dict[str, Any]]:
    content = llm.requests[-1].messages[-1]["content"]
    assert isinstance(content, list)
    return content


async def test_valid_answer_is_returned() -> None:
    llm = FakeLLM({"tester": Script([final_answer({"city": "Lyon", "score": 7})])})
    assert await _run(llm) == Answer(city="Lyon", score=7)
    request = llm.requests[0]
    assert request.output_schema is not None
    assert request.prompt_version.startswith("tester@")


async def test_tool_results_are_sent_back_to_the_model() -> None:
    seen: list[dict[str, Any]] = []

    async def lookup(tool_input: dict[str, Any]) -> str:
        seen.append(tool_input)
        return "Lyon"

    llm = FakeLLM(
        {
            "tester": Script(
                [tool_use("lookup", {"q": "x"}), final_answer({"city": "Lyon", "score": 1})]
            )
        }
    )
    await _run(llm, tools={"lookup": (LOOKUP, lookup)})
    assert seen == [{"q": "x"}]
    result = _last_tool_results(llm)[0]
    assert result == {
        "type": "tool_result",
        "tool_use_id": "toolu_fake_1",
        "content": "Lyon",
        "is_error": False,
    }


async def test_unknown_tool_is_refused_but_run_continues() -> None:
    llm = FakeLLM(
        {"tester": Script([tool_use("send_email", {}), final_answer({"city": "Nice", "score": 2})])}
    )
    assert (await _run(llm)).city == "Nice"
    result = _last_tool_results(llm)[0]
    assert result["is_error"] is True
    assert "Unknown tool 'send_email'" in result["content"]


async def test_tool_failure_is_reported_to_the_model() -> None:
    async def failing(_tool_input: dict[str, Any]) -> str:
        raise ToolFailure("Page not reachable")

    llm = FakeLLM(
        {"tester": Script([tool_use("lookup", {}), final_answer({"city": "Pau", "score": 3})])}
    )
    await _run(llm, tools={"lookup": (LOOKUP, failing)})
    assert _last_tool_results(llm)[0] == {
        "type": "tool_result",
        "tool_use_id": "toolu_fake_1",
        "content": "Page not reachable",
        "is_error": True,
    }


async def test_tool_budget_is_enforced() -> None:
    async def lookup(_tool_input: dict[str, Any]) -> str:
        return "ok"

    llm = FakeLLM(
        {"tester": Script([tool_use("lookup", {}), final_answer({"city": "Metz", "score": 4})])}
    )
    await _run(llm, tools={"lookup": (LOOKUP, lookup)}, max_tool_calls=0)
    assert "Tool budget exhausted" in _last_tool_results(llm)[0]["content"]


async def test_invalid_output_gets_one_retry_with_the_errors() -> None:
    llm = FakeLLM(
        {
            "tester": Script(
                [
                    final_answer({"city": "Caen", "score": 42}),
                    final_answer({"city": "Caen", "score": 9}),
                ]
            )
        }
    )
    assert (await _run(llm)).score == 9
    feedback = llm.requests[-1].messages[-1]["content"]
    assert "did not pass validation" in feedback
    assert "score" in feedback


async def test_invalid_output_twice_fails_cleanly() -> None:
    llm = FakeLLM({"tester": Script([final_answer("not json")])})
    with pytest.raises(AgentError) as exc_info:
        await _run(llm)
    assert exc_info.value.details["reason"] == "invalid_output"


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
async def test_abnormal_stops_fail_explicitly(stop_reason: str) -> None:
    llm = FakeLLM({"tester": Script([stop(stop_reason)])})
    with pytest.raises(AgentError) as exc_info:
        await _run(llm)
    assert exc_info.value.details["reason"] == stop_reason


async def test_endless_tool_calls_hit_the_step_limit() -> None:
    llm = FakeLLM({"tester": Script([tool_use("lookup", {})])})
    with pytest.raises(AgentError) as exc_info:
        await _run(llm, max_tool_calls=1)
    assert exc_info.value.details["reason"] == "too_many_steps"


def test_prompt_version_changes_with_content() -> None:
    assert Prompt("a", "one").version != Prompt("a", "two").version
    assert load_prompt("offer_analyst").version.startswith("offer_analyst@")
