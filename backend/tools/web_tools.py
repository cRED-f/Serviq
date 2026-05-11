from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import httpx
from bs4 import BeautifulSoup

from tools.base import ToolDefinition, ToolExecutionContext, ToolResult, ToolRisk

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
BASE_URL = "https://html.duckduckgo.com/html"


@dataclass
class SearchResult:
    title: str
    link: str
    snippet: str
    position: int


class RateLimiter:
    def __init__(self, requests_per_minute: int = 30):
        self.requests_per_minute = requests_per_minute
        self.requests: list[datetime] = []

    async def acquire(self):
        now = datetime.now()
        self.requests = [
            req for req in self.requests if now - req < timedelta(minutes=1)
        ]
        if len(self.requests) >= self.requests_per_minute:
            wait_time = 60 - (now - self.requests[0]).total_seconds()
            if wait_time > 0:
                import asyncio
                await asyncio.sleep(wait_time)
        self.requests.append(now)


_search_limiter = RateLimiter()


async def _search_ddg(
    query: str, max_results: int = 10, region: str = ""
) -> list[SearchResult]:
    await _search_limiter.acquire()

    data = {
        "q": query,
        "b": "",
        "kl": region,
        "kp": "-1",
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            BASE_URL, data=data, headers=HEADERS, timeout=30.0
        )
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    for result in soup.select(".result"):
        title_elem = result.select_one(".result__title")
        if not title_elem:
            continue

        link_elem = title_elem.find("a")
        if not link_elem:
            continue

        title = link_elem.get_text(strip=True)
        link = link_elem.get("href", "")

        if "y.js" in link:
            continue

        if link.startswith("//duckduckgo.com/l/?uddg="):
            link = urllib.parse.unquote(link.split("uddg=")[1].split("&")[0])

        snippet_elem = result.select_one(".result__snippet")
        snippet = snippet_elem.get_text(strip=True) if snippet_elem else ""

        results.append(SearchResult(
            title=title,
            link=link,
            snippet=snippet,
            position=len(results) + 1,
        ))

        if len(results) >= max_results:
            break

    return results


async def _format_results_for_llm(results: list[SearchResult]) -> str:
    if not results:
        return "No results were found for your search query."

    output = [f"Found {len(results)} search results:\n"]
    for result in results:
        output.append(f"{result.position}. {result.title}")
        output.append(f"   URL: {result.link}")
        output.append(f"   Summary: {result.snippet}")
        output.append("")

    return "\n".join(output)


async def _fetch_content(url: str, start_index: int = 0, max_length: int = 8000) -> str:
    await _search_limiter.acquire()

    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            headers={**HEADERS, "Accept": "text/html"},
            follow_redirects=True,
            timeout=30.0,
        )
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    for element in soup(["script", "style", "nav", "header", "footer"]):
        element.decompose()

    text = soup.get_text()
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    text = " ".join(chunk for chunk in chunks if chunk)
    text = re.sub(r"\s+", " ", text).strip()

    total_length = len(text)
    text = text[start_index:start_index + max_length]
    is_truncated = start_index + max_length < total_length

    metadata = f"\n\n---\n[Content info: Showing characters {start_index}-{start_index + len(text)} of {total_length} total"
    if is_truncated:
        metadata += f". Use start_index={start_index + max_length} to see more"
    metadata += "]"

    return text + metadata


async def web_search_tool(args: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
    query = str(args.get("query", "")).strip()
    if not query:
        return ToolResult(
            name="web_search",
            ok=False,
            risk=ToolRisk.LOW,
            error="Query is required",
        )

    max_results = min(int(args.get("max_results", 10)), 20)
    region = str(args.get("region", ""))

    try:
        results = await _search_ddg(query, max_results, region)
        output = await _format_results_for_llm(results)
        return ToolResult(
            name="web_search",
            ok=True,
            risk=ToolRisk.LOW,
            output=output,
            metadata={"result_count": len(results)},
        )
    except httpx.TimeoutException:
        return ToolResult(
            name="web_search",
            ok=False,
            risk=ToolRisk.LOW,
            error="Search request timed out",
        )
    except httpx.HTTPStatusError as e:
        return ToolResult(
            name="web_search",
            ok=False,
            risk=ToolRisk.LOW,
            error=f"HTTP error: {e.response.status_code}",
        )
    except Exception as e:
        return ToolResult(
            name="web_search",
            ok=False,
            risk=ToolRisk.LOW,
            error=f"Search failed: {str(e)}",
        )


async def web_fetch_tool(args: dict[str, Any], context: ToolExecutionContext) -> ToolResult:
    url = str(args.get("url", "")).strip()
    if not url:
        return ToolResult(
            name="web_fetch",
            ok=False,
            risk=ToolRisk.LOW,
            error="URL is required",
        )

    if not url.startswith(("http://", "https://")):
        return ToolResult(
            name="web_fetch",
            ok=False,
            risk=ToolRisk.LOW,
            error="URL must start with http:// or https://",
        )

    start_index = int(args.get("start_index", 0))
    max_length = min(int(args.get("max_length", 8000)), 20000)

    try:
        content = await _fetch_content(url, start_index, max_length)
        return ToolResult(
            name="web_fetch",
            ok=True,
            risk=ToolRisk.LOW,
            output=content,
        )
    except httpx.TimeoutException:
        return ToolResult(
            name="web_fetch",
            ok=False,
            risk=ToolRisk.LOW,
            error="Request timed out",
        )
    except httpx.HTTPStatusError as e:
        return ToolResult(
            name="web_fetch",
            ok=False,
            risk=ToolRisk.LOW,
            error=f"HTTP error: {e.response.status_code}",
        )
    except Exception as e:
        return ToolResult(
            name="web_fetch",
            ok=False,
            risk=ToolRisk.LOW,
            error=f"Failed to fetch: {str(e)}",
        )


WEB_TOOL_DEFINITIONS = [
    ToolDefinition(
        name="web_search",
        description="Search the web using DuckDuckGo. Returns a list of results with titles, URLs, and snippets. Use this to find current information, research topics, or locate specific websites. For best results, use specific and descriptive search queries.",
        risk=ToolRisk.LOW,
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string. Be specific for better results.",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return, between 1 and 20",
                    "default": 10,
                },
                "region": {
                    "type": "string",
                    "description": "Region/language code (e.g., 'us-en', 'uk-en', 'de-de')",
                    "default": "",
                },
            },
            "required": ["query"],
        },
        handler=web_search_tool,
    ),
    ToolDefinition(
        name="web_fetch",
        description="Fetch and extract the main text content from a webpage. Strips out navigation, headers, footers, scripts, and styles to return clean readable text. Use this after searching to read the full content of a specific result.",
        risk=ToolRisk.LOW,
        parameters={
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The full URL of the webpage to fetch (must start with http:// or https://)",
                },
                "start_index": {
                    "type": "integer",
                    "description": "Character offset to start reading from",
                    "default": 0,
                },
                "max_length": {
                    "type": "integer",
                    "description": "Maximum number of characters to return",
                    "default": 8000,
                },
            },
            "required": ["url"],
        },
        handler=web_fetch_tool,
    ),
]