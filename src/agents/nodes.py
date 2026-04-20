import os
from typing import Any, Dict

import ssl
import urllib3
import trafilatura
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END
from langgraph.types import Command
from loguru import logger
from tavily import TavilyClient

from src.agents.agents import (
    orchestrator_agent,
    speaker_selector_agent,
    web_searcher_agent,
    web_scraper_agent,
    research_analyst_agent,
    answer_refiner_agent,
)
from src.agents.state import GraphState
from src.agents.utils import format_history

# Disable SSL verification for requests
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['CURL_CA_BUNDLE'] = ''

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

import urllib3.util.ssl_
def create_urllib3_context_no_verify(*args, **kwargs):
    context = urllib3.util.ssl_.create_urllib3_context_original(*args, **kwargs)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context

urllib3.util.ssl_.create_urllib3_context_original = urllib3.util.ssl_.create_urllib3_context
urllib3.util.ssl_.create_urllib3_context = create_urllib3_context_no_verify

tavily_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))

# Hard cap on scraped characters per URL to keep the context window manageable.
SCRAPE_MAX_CHARS_PER_URL = 6000
SCRAPE_MAX_URLS = 3


def _dedup(urls):
    seen = set()
    out = []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


def speaker_selector_node(state: GraphState) -> str:
    if state.get("resolved", False):
        logger.debug("Answer already refined, terminating conversation.")
        return Command(goto=END, update={"next": END, "resolved": False})

    executed = state.get("executed_agents", [])
    pipeline = state.get("pipeline", []) or []
    remaining = [a for a in pipeline if a not in executed]

    context = (
        f"planned_pipeline: {pipeline}\n"
        f"executed_agents: {executed}\n"
        f"remaining_pipeline: {remaining}"
    )

    speaker = None
    try:
        result = speaker_selector_agent.invoke({"context": context})
        speaker = result.speaker if result else None
    except Exception as e:
        logger.warning(f"Speaker Selector structured output failed: {e}")

    # Minimal safety net: only engages when the LLM returns nothing or an
    # already-executed name. No plan parsing, no ordering logic.
    if speaker is None or speaker in executed:
        if speaker in executed:
            logger.warning(f"Speaker Selector picked already-executed '{speaker}', overriding.")
        speaker = remaining[0] if remaining else "answer_refiner"
        if speaker == "answer_refiner" and "answer_refiner" in executed:
            speaker = "END"
        logger.warning(f"Speaker Selector fallback chose: {speaker}")

    logger.debug(f"Speaker Selector selected next speaker: {speaker}")
    if speaker == "END":
        speaker = END

    return Command(goto=speaker, update={"next": speaker})


VALID_PIPELINE_AGENTS = {"web_searcher", "web_scraper", "research_analyst", "answer_refiner"}


def _normalize_pipeline(pipeline: list[str]) -> list[str]:
    """Deduplicate, drop invalid entries, enforce invariants: research_analyst
    whenever search/scrape is present, and answer_refiner always last."""
    seen = set()
    out = []
    for a in pipeline:
        if a in VALID_PIPELINE_AGENTS and a not in seen:
            seen.add(a)
            out.append(a)

    if ("web_searcher" in out or "web_scraper" in out) and "research_analyst" not in out:
        if "answer_refiner" in out:
            out.insert(out.index("answer_refiner"), "research_analyst")
        else:
            out.append("research_analyst")

    if "answer_refiner" in out:
        out.remove("answer_refiner")
    out.append("answer_refiner")
    return out


def orchestrator_node(state: GraphState) -> Dict[str, Any]:
    context = f"""
        History: {format_history(state.get("messages", []))},
        Question: {state.get("question", "")}
    """

    pipeline: list[str] = []
    reasoning = ""
    try:
        result = orchestrator_agent.invoke({"context": context})
        if result is not None:
            pipeline = list(result.pipeline)
            reasoning = result.reasoning
    except Exception as e:
        logger.warning(f"Orchestrator structured output failed: {e}")

    if not pipeline:
        pipeline = ["answer_refiner"]
        reasoning = reasoning or "Fallback: orchestrator failed to produce a pipeline."

    pipeline = _normalize_pipeline(pipeline)
    plan_text = f"{reasoning}\nPipeline: {' -> '.join(pipeline)}"

    logger.warning(f"Orchestrator plan: {plan_text}")
    return {
        "messages": [HumanMessage(content=state.get("question", ""))],
        "plan": plan_text,
        "pipeline": pipeline,
        "executed_agents": state.get("executed_agents", []) + ['orchestrator'],
    }


def web_searcher_node(state: GraphState) -> Dict[str, Any]:
    """Generates a search query and executes it via Tavily."""
    question = state.get("question", "")
    plan = state.get("plan", "")

    search_query = web_searcher_agent.invoke({"question": question, "plan": plan})
    logger.info(f"Web Searcher generated query: {search_query}")

    results = []
    urls = []
    try:
        response = tavily_client.search(query=search_query, max_results=5)
        for r in response.get("results", []):
            results.append(f"Title: {r['title']}\nURL: {r['url']}\nContent: {r['content']}\n")
            urls.append(r['url'])
        search_results = "\n---\n".join(results)
    except Exception as e:
        logger.error(f"Tavily search failed: {e}")
        search_results = f"Search failed: {str(e)}"

    logger.info(f"Web Searcher found {len(results)} results")
    return {
        "search_results": search_results,
        "cited_urls": _dedup(state.get("cited_urls", []) + urls),
        "executed_agents": state.get("executed_agents", []) + ['web_searcher'],
    }


def web_scraper_node(state: GraphState) -> Dict[str, Any]:
    """Picks URLs (from search results, plan, or constructed) and scrapes them with trafilatura."""
    question = state.get("question", "")
    plan = state.get("plan", "")
    search_results = state.get("search_results", "") or "(no prior search results)"
    history = format_history(state.get("messages", []))

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

    scraped_content = "\n---\n".join(scraped_blocks) if scraped_blocks else "(no content extracted)"

    return {
        "scraped_content": scraped_content,
        "cited_urls": _dedup(state.get("cited_urls", []) + successful_urls),
        "executed_agents": state.get("executed_agents", []) + ['web_scraper'],
    }


def research_analyst_node(state: GraphState) -> Dict[str, Any]:
    """Analyzes raw search results + scraped content and produces structured insights."""
    question = state.get("question", "")
    search_results = state.get("search_results", "") or "(none)"
    scraped_content = state.get("scraped_content", "") or "(none)"

    analysis = research_analyst_agent.invoke({
        "question": question,
        "search_results": search_results,
        "scraped_content": scraped_content,
    })
    logger.info(f"Research Analyst produced analysis: {analysis[:200]}...")

    return {
        "messages": [AIMessage(content=f"[Research Analysis]\n{analysis}")],
        "executed_agents": state.get("executed_agents", []) + ['research_analyst'],
    }


def answer_refiner_node(state: GraphState) -> Dict[str, Any]:
    cited_urls = state.get("cited_urls", [])
    context = f"""
        History: {[msg.content for msg in state.get("messages", [])]},
        Question: {state.get("question", "")},
        Multi-Agent framework solution plan: {state.get("plan", "")},
        Search Results: {state.get("search_results", "")},
        Scraped Content: {state.get("scraped_content", "")},
        cited_urls: {cited_urls}
    """
    answer = answer_refiner_agent.invoke({"context": context})
    logger.info(f"Refined answer: {answer}")
    return {
        "messages": AIMessage(content=answer),
        "plan": "",
        "executed_agents": state.get("executed_agents", []) + ['answer_refiner'],
        "resolved": True,
    }
