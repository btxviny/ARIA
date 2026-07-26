import os
from typing import Any, Dict
from urllib.parse import urlparse

import httpx
from loguru import logger
from tavily import TavilyClient

from src.agents.agents import web_searcher_agent
from src.agents.nodes._common import NO_SEARCH_RESULTS
from src.agents.state import GraphState
from src.agents.utils import dedup_urls, format_history

tavily_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))


def _favicon_url(url: str) -> str:
    try:
        domain = urlparse(url).netloc
        return f"https://www.google.com/s2/favicons?domain={domain}&sz=32"
    except Exception:
        return ""


def _summarize_search_error(error: Exception) -> str:
    """Collapse noisy provider/network errors into a short operator-facing reason."""
    message = " ".join(str(error).split())
    lowered = message.lower()

    if "zscaler" in lowered:
        return "Tavily web search was blocked by the network proxy (Zscaler)."
    if "forbidden" in lowered:
        return "Tavily web search was rejected with a forbidden response."
    if isinstance(error, httpx.TimeoutException):
        return "Tavily web search timed out."
    if isinstance(error, httpx.HTTPError):
        return "Tavily web search failed because of an HTTP/network error."

    if len(message) > 240:
        message = message[:237] + "..."
    return f"Tavily web search failed: {message}"


def web_searcher_node(state: GraphState) -> Dict[str, Any]:
    """Generates a search query and executes it via Tavily."""
    question = state.get("question", "")
    plan = state.get("plan", "")
    history = format_history(state.get("messages", []), state.get("summary", ""))

    search_query = web_searcher_agent.invoke({"question": question, "plan": plan, "history": history})
    logger.info(f"Web Searcher generated query: {search_query}")

    results = []
    urls = []
    cards = []
    search_status = "ok"
    search_error = ""
    try:
        response = tavily_client.search(query=search_query, max_results=5)
        for r in response.get("results", []):
            results.append(f"Title: {r['title']}\nURL: {r['url']}\nContent: {r['content']}\n")
            urls.append(r['url'])
            cards.append({
                "title": r.get("title", ""),
                "url": r["url"],
                "snippet": r.get("content", "")[:200],
                "favicon_url": _favicon_url(r["url"]),
            })
        search_results = "\n---\n".join(results) if results else NO_SEARCH_RESULTS
        if not results:
            search_status = "empty"
    except Exception as e:
        search_status = "failed"
        search_error = _summarize_search_error(e)
        logger.error(f"Tavily search failed: {search_error}")
        search_results = f"(web search unavailable: {search_error})"

    logger.info(f"Web Searcher found {len(results)} results")
    existing_cards = state.get("web_result_cards", [])
    return {
        "search_results": search_results,
        "search_status": search_status,
        "search_error": search_error,
        "cited_urls": dedup_urls(state.get("cited_urls", []) + urls),
        "web_result_cards": existing_cards + cards,
        "executed_agents": state.get("executed_agents", []) + ['web_searcher'],
    }
