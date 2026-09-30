"""Specialised LLM agents.

Convention: one agent = one module + one versioned system prompt in `prompts/<agent>.md`
+ one Pydantic output schema. Agents that read external content never get action tools.
"""
