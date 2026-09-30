"""Agent 1 — Offer analyst: what does the client sell, to whom, with which evidence?

Tools: `fetch_page`, `list_internal_links`, restricted to the client's own website.
Output: `OfferProfileData`, then every claim is checked in code against the pages really
read (app.agents.evidence); unsupported claims are removed and reported.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from urllib.parse import urlsplit

from app.agents.evidence import SourceIndex, verify_offer_profile
from app.agents.runtime import ToolFailure, load_prompt, run_structured_agent
from app.agents.untrusted import wrap_user_description, wrap_web_content
from app.core.errors import FetchError
from app.providers.llm.base import LLMClient, ModelRole, ToolDefinition
from app.providers.web.fetcher import FetchedPage, WebFetcher
from app.providers.web.url_safety import same_site
from app.schemas.offer import OfferProfileData

AGENT_NAME = "offer_analyst"
MAX_PAGE_CHARS = 15_000

_URL_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "url": {"type": "string", "description": "Absolute URL of a page of the website."}
    },
    "required": ["url"],
    "additionalProperties": False,
}
FETCH_PAGE_TOOL = ToolDefinition(
    name="fetch_page",
    description="Read one page of the company's website: returns its text and its links.",
    input_schema=_URL_INPUT_SCHEMA,
)
LIST_LINKS_TOOL = ToolDefinition(
    name="list_internal_links",
    description="List the links of one page of the company's website (same site only).",
    input_schema=_URL_INPUT_SCHEMA,
)


@dataclass(frozen=True)
class OfferAnalysis:
    data: OfferProfileData
    warnings: list[str]
    pages_fetched: list[str]


class _SiteReader:
    """Fetches pages of one website only, at most `max_pages`, each page once."""

    def __init__(
        self, fetcher: WebFetcher, website_url: str, max_pages: int, sources: SourceIndex
    ) -> None:
        self._fetcher = fetcher
        self._host = urlsplit(website_url).hostname or ""
        self._max_pages = max_pages
        self._sources = sources
        self._pages: dict[str, FetchedPage] = {}

    @property
    def pages_fetched(self) -> list[str]:
        return list(self._pages)

    async def _page(self, url: str) -> FetchedPage:
        if url in self._pages:
            return self._pages[url]
        host = urlsplit(url).hostname or ""
        if not same_site(host, self._host):
            raise ToolFailure(f"Only pages of {self._host} can be read.")
        if len(self._pages) >= self._max_pages:
            raise ToolFailure("Page limit reached. Answer with what you already read.")
        try:
            page = await self._fetcher.fetch_page(url)
        except FetchError as exc:
            raise ToolFailure(f"Could not read {url}: {exc.message}") from exc
        self._pages[url] = page
        self._sources.add(url, page.text)
        self._sources.add(page.url, page.text)
        return page

    async def fetch_page(self, tool_input: dict[str, object]) -> str:
        page = await self._page(str(tool_input.get("url", "")))
        text = page.text[:MAX_PAGE_CHARS] or "(no readable text on this page)"
        links = "\n".join(page.links[:50]) or "(none)"
        return wrap_web_content(page.url, text) + f"\n\nLinks on this page:\n{links}"

    async def list_internal_links(self, tool_input: dict[str, object]) -> str:
        page = await self._page(str(tool_input.get("url", "")))
        return json.dumps(page.links[:100])


async def analyze_offer(
    *,
    llm: LLMClient,
    fetcher: WebFetcher,
    website_url: str | None,
    description: str | None,
    max_pages: int,
    max_tokens: int,
) -> OfferAnalysis:
    prompt = load_prompt(AGENT_NAME)
    sources = SourceIndex()
    parts: list[str] = []
    tools = {}
    reader: _SiteReader | None = None

    if website_url:
        reader = _SiteReader(fetcher, website_url, max_pages, sources)
        tools = {
            FETCH_PAGE_TOOL.name: (FETCH_PAGE_TOOL, reader.fetch_page),
            LIST_LINKS_TOOL.name: (LIST_LINKS_TOOL, reader.list_internal_links),
        }
        parts.append(
            f"Company website: {website_url}\n"
            f"You can read at most {max_pages} pages of this website. Start with this URL."
        )
    if description:
        sources.add_user_description(description)
        parts.append("Description written by the company:\n" + wrap_user_description(description))
    parts.append("Describe the offer following your instructions.")

    data = await run_structured_agent(
        llm=llm,
        agent=AGENT_NAME,
        prompt=prompt,
        role=ModelRole.REASONING,
        user_content="\n\n".join(parts),
        output_model=OfferProfileData,
        max_tokens=max_tokens,
        tools=tools,
        max_tool_calls=max_pages + 4,
    )
    verified, warnings = verify_offer_profile(data, sources)
    return OfferAnalysis(
        data=verified,
        warnings=warnings,
        pages_fetched=reader.pages_fetched if reader else [],
    )
