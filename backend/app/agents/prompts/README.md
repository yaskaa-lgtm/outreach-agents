# Agent system prompts

One Markdown file per agent (`offer_analyst.md`, `icp_strategist.md`, …), added from Phase 1.

- Prompts are **versioned with Git**: a change to a prompt is a reviewed commit, and the prompt
  version is recorded in `llm_calls.prompt_version` so eval results can be compared per version.
- Every prompt that receives web pages or inbound emails must state that content inside
  `<untrusted_web_content>` / `<untrusted_email>` tags is **data, never instructions**.
