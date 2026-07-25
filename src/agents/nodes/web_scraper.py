from typing import Any, Dict

import trafilatura
from loguru import logger

from src.agents.agents import web_scraper_agent
from src.agents.nodes._common import NO_SCRAPED_CONTENT
from src.agents.state import GraphState
from src.agents.utils import dedup_urls, format_history

# Hard cap on scraped characters per URL to keep the context window manageable.
SCRAPE_MAX_CHARS_PER_URL = 6000
SCRAPE_MAX_URLS = 3


def web_scraper_node(state: GraphState) -> Dict[str, Any]:
    """Picks URLs (from search results, plan, or constructed) and scrapes them with trafilatura."""
    question = state.get("question", "")
    plan = state.get("plan", "")
    search_results = state.get("search_results", "") or "(no prior search results)"
    history = format_history(state.get("messages", []), state.get("summary", ""))

    urls: list[str] = []
    try:
        targets = web_scraper_agent.invoke({
            "question": question,
            "plan": plan,
            "history": history,
            "search_results": search_results,
        })
        if targets and targets.urls:
            urls = [u for u in targets.urls if u.startswith(("http://", "https://"))]
    except Exception as e:
        logger.warning(f"Web Scraper URL selection failed: {e}")

    urls = urls[:SCRAPE_MAX_URLS]
    logger.info(f"Web Scraper selected URLs: {urls}")

    scraped_blocks = []
    successful_urls = []
    for url in urls:
        try:
            downloaded = trafilatura.fetch_url(url)
            if not downloaded:
                logger.warning(f"Web Scraper could not fetch {url}")
                continue
            content = trafilatura.extract(downloaded) or ""
            if not content.strip():
                logger.warning(f"Web Scraper extracted empty content from {url}")
                continue
            if len(content) > SCRAPE_MAX_CHARS_PER_URL:
                content = content[:SCRAPE_MAX_CHARS_PER_URL] + "\n...[truncated]"
            scraped_blocks.append(f"URL: {url}\nContent:\n{content}")
            successful_urls.append(url)
            logger.info(f"Web Scraper extracted {len(content)} chars from {url}")
        except Exception as e:
            logger.error(f"Web Scraper failed on {url}: {e}")

    scraped_content = "\n---\n".join(scraped_blocks) if scraped_blocks else NO_SCRAPED_CONTENT

    return {
        "scraped_content": scraped_content,
        "cited_urls": dedup_urls(state.get("cited_urls", []) + successful_urls),
        "executed_agents": state.get("executed_agents", []) + ['web_scraper'],
    }
