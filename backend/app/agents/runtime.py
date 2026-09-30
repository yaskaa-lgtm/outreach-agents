"""Shared agent loop: tool calls, structured output, one retry on invalid output.

Rules enforced here for every agent:
- the model can only call the tools the agent declares (unknown names are refused);
- tool errors are returned to the model as `is_error` results, never raised;
- the final answer must validate against the agent's Pydantic model; on failure the model
  gets exactly one retry with the validation errors, then the run fails cleanly;
- `refusal` and `max_tokens` stop reasons end the run with an explicit error.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from functools import cache
from importlib.resources import files
from typing import Any

import anthropic
from pydantic import BaseModel, ValidationError

from app.core.errors import AgentError
from app.providers.llm.base import LLMClient, LLMRequest, ModelRole, ToolDefinition

ToolHandler = Callable[[dict[str, Any]], Awaitable[str]]


class ToolFailure(Exception):
    """Raised by a tool handler; the message is shown to the model as the tool result."""


@dataclass(frozen=True)
class Prompt:
    name: str
    text: str

    @property
    def version(self) -> str:
        """Content hash: any edit to the prompt file produces a new version."""
        digest = hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:12]
        return f"{self.name}@{digest}"


@cache
def load_prompt(name: str) -> Prompt:
    text = files("app.agents").joinpath("prompts", f"{name}.md").read_text(encoding="utf-8")
    return Prompt(name=name, text=text)


def output_schema(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema accepted by structured outputs (constraints it cannot express are moved
    into descriptions by the SDK; Pydantic still enforces them afterwards)."""
    return anthropic.transform_schema(model)


async def run_structured_agent[T: BaseModel](
    *,
    llm: LLMClient,
    agent: str,
    prompt: Prompt,
    role: ModelRole,
    user_content: str,
    output_model: type[T],
    max_tokens: int,
    tools: Mapping[str, tuple[ToolDefinition, ToolHandler]] | None = None,
    max_tool_calls: int = 0,
) -> T:
    tools = tools or {}
    definitions = [definition for definition, _handler in tools.values()]
    schema = output_schema(output_model)
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_content}]
    tool_calls_used = 0
    retried_invalid_output = False
    # Hard cap on model turns, whatever happens.
    for _turn in range(max_tool_calls + 4):
        response = await llm.complete(
            LLMRequest(
                agent=agent,
                prompt_version=prompt.version,
                role=role,
                system=prompt.text,
                messages=list(messages),  # snapshot: later turns must not alter it
                max_tokens=max_tokens,
                tools=definitions,
                output_schema=schema,
            )
        )
        if response.stop_reason == "refusal":
            raise AgentError("The model declined this request.", agent=agent, reason="refusal")
        if response.stop_reason == "max_tokens":
            raise AgentError(
                "The model answer was cut off (max_tokens).", agent=agent, reason="max_tokens"
            )

        messages.append({"role": "assistant", "content": response.assistant_content})

        if response.tool_calls:
            results = []
            for call in response.tool_calls:
                tool_calls_used += 1
                content, is_error = await _run_tool(
                    tools, call.name, call.input, tool_calls_used, max_tool_calls
                )
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": content,
                        "is_error": is_error,
                    }
                )
            messages.append({"role": "user", "content": results})
            continue

        try:
            return output_model.model_validate_json(response.text)
        except ValidationError as exc:
            if retried_invalid_output:
                raise AgentError(
                    "The model returned invalid output twice.", agent=agent, reason="invalid_output"
                ) from exc
            retried_invalid_output = True
            messages.append({"role": "user", "content": _validation_feedback(exc)})

    raise AgentError(
        "The agent did not finish within its step limit.", agent=agent, reason="too_many_steps"
    )


async def _run_tool(
    tools: Mapping[str, tuple[ToolDefinition, ToolHandler]],
    name: str,
    tool_input: dict[str, Any],
    calls_used: int,
    max_calls: int,
) -> tuple[str, bool]:
    if name not in tools:
        return f"Unknown tool '{name}'. Available tools: {', '.join(tools) or 'none'}.", True
    if calls_used > max_calls:
        return "Tool budget exhausted. Answer now with the information you already have.", True
    _definition, handler = tools[name]
    try:
        return await handler(tool_input), False
    except ToolFailure as exc:
        return str(exc), True


def _validation_feedback(exc: ValidationError) -> str:
    errors = [
        {"location": ".".join(str(part) for part in error["loc"]), "problem": error["msg"]}
        for error in exc.errors(include_url=False, include_input=False)
    ][:20]
    return (
        "Your previous answer did not pass validation. Fix these problems and answer again "
        "with the complete JSON only:\n" + json.dumps(errors, ensure_ascii=False, indent=1)
    )
