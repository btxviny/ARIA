from typing import Any, Dict

from langchain_core.messages import AIMessage
from loguru import logger

from src.agents.agents import research_analyst_agent
from src.agents.nodes._common import NO_RAG_RESULTS, NO_SCRAPED_CONTENT, NO_SEARCH_RESULTS
from src.agents.state import GraphState


def research_analyst_node(state: GraphState) -> Dict[str, Any]:
    """Analyzes raw search results, scraped content, and RAG document context to produce structured insights."""
    question = state.get("question", "")
    search_results = state.get("search_results", "") or "(none)"
    scraped_content = state.get("scraped_content", "") or "(none)"
    rag_context = state.get("rag_context", "") or "(none)"
    search_status = state.get("search_status", "")
    search_error = state.get("search_error", "")
    has_rag_content = rag_context not in ("(none)", NO_RAG_RESULTS)

    if search_status == "failed" and scraped_content == NO_SCRAPED_CONTENT and not has_rag_content:
        analysis = (
            "Insufficient source material to answer the question. "
            f"Live web search is unavailable: {search_error} "
            "No pages were scraped successfully, so there are no verifiable sources to analyze."
        )
    elif search_results == NO_SEARCH_RESULTS and scraped_content == NO_SCRAPED_CONTENT and not has_rag_content:
        analysis = (
            "Insufficient source material to answer the question. "
            "The web search returned no results, no pages were scraped successfully, "
            "and no relevant content was found in the user's uploaded sources."
        )
    else:
        analysis = research_analyst_agent.invoke({
            "question": question,
            "search_results": search_results,
            "scraped_content": scraped_content,
            "rag_context": rag_context,
        })

    logger.info(f"Research Analyst produced analysis: {analysis[:200]}...")

    return {
        "messages": [AIMessage(content=f"[Research Analysis]\n{analysis}")],
        "executed_agents": state.get("executed_agents", []) + ['research_analyst'],
    }
