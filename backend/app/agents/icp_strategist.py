"""Agent 2 — ICP strategist: 3 to 6 segments with searchable criteria and a fit score.

No tools: it only reasons on the validated offer profile. Its criteria are validated
against official NAF, headcount and département lists (app.schemas.segment); an invalid
code triggers the one-retry-with-errors mechanism of the agent runtime.
"""

from __future__ import annotations

from app.agents.runtime import load_prompt, run_structured_agent
from app.agents.untrusted import wrap_offer_profile
from app.providers.llm.base import LLMClient, ModelRole
from app.schemas.offer import OfferProfileData
from app.schemas.segment import SegmentStrategy

AGENT_NAME = "icp_strategist"


async def propose_segments(
    *, llm: LLMClient, offer: OfferProfileData, max_tokens: int
) -> SegmentStrategy:
    user_content = (
        "Validated offer profile:\n"
        + wrap_offer_profile(offer.model_dump_json(indent=1))
        + "\n\nPropose the segments following your instructions."
    )
    return await run_structured_agent(
        llm=llm,
        agent=AGENT_NAME,
        prompt=load_prompt(AGENT_NAME),
        role=ModelRole.REASONING,
        user_content=user_content,
        output_model=SegmentStrategy,
        max_tokens=max_tokens,
    )
