"""Anonymous Parallel Search MCP fulfilments for configured chatbot intents."""

import asyncio
import json
from datetime import timedelta
from urllib.parse import urlsplit

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

MCP_URL = "https://search.parallel.ai/mcp"
USER_AGENT = "ai-chatbot-framework/ParallelSearch"
TIMEOUT_SECONDS = 30


class WebSearchError(Exception):
    """A web fulfilment failed without changing the selected fulfilment."""


def _http_url(value: str) -> bool:
    try:
        url = urlsplit(value)
        return url.scheme in ("http", "https") and bool(url.hostname)
    except ValueError:
        return False


async def call_web_tool(tool: str, query: str, session_id: str) -> dict:
    """Run one search or page fetch, retaining the caller's conversation UUID.

    The endpoint and transport are fixed. Neither ambient API keys nor an
    intent's REST credentials are used. Cancellation propagates to the SDK.
    """
    if not query:
        raise WebSearchError("A query or page URL is required")
    if tool == "web_search":
        arguments = {"objective": query, "search_queries": [query]}
    elif tool == "web_fetch" and _http_url(query):
        arguments = {"urls": [query]}
    else:
        raise WebSearchError("Unsupported tool or invalid HTTP(S) page URL")
    arguments["session_id"] = session_id

    try:
        # Bound the complete operation, including discovery and stream cleanup.
        async with asyncio.timeout(TIMEOUT_SECONDS):
            async with (
                httpx.AsyncClient(
                    headers={"User-Agent": USER_AGENT},
                    timeout=httpx.Timeout(TIMEOUT_SECONDS),
                ) as http_client,
                streamable_http_client(MCP_URL, http_client=http_client) as (
                    read,
                    write,
                    _,
                ),
            ):
                async with ClientSession(
                    read,
                    write,
                    read_timeout_seconds=timedelta(seconds=TIMEOUT_SECONDS),
                ) as client:
                    await client.initialize()
                    tools = await client.list_tools()
                    if tool not in {item.name for item in tools.tools}:
                        raise WebSearchError("The selected web tool is unavailable")
                    result = await client.call_tool(tool, arguments)
                    if result.isError:
                        raise WebSearchError(
                            "The web service could not fulfil the request"
                        )
                    payload = result.structuredContent
                    if payload is None:
                        # Older MCP servers encode their result as JSON text.
                        text = "\n".join(
                            item.text for item in result.content if item.type == "text"
                        )
                        payload = json.loads(text)
                    if not isinstance(payload, dict) or not isinstance(
                        payload.get("results"), list
                    ):
                        raise WebSearchError("Invalid web result")
                    # Only HTTP(S) source links may reach response templates.
                    payload["results"] = [
                        item
                        for item in payload["results"]
                        if isinstance(item, dict) and _http_url(item.get("url", ""))
                    ]
                    return payload
    except Exception as exc:
        # SDK transport errors can be nested exception groups. Preserve the
        # cause privately while giving the dialogue manager one failure type.
        raise WebSearchError("Web fulfilment is unavailable") from exc
