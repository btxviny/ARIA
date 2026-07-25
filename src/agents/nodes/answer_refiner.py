from typing import Any, Dict

from langchain_core.messages import AIMessage
from loguru import logger

from src.agents.agents import answer_refiner_agent
from src.agents.state import GraphState


def answer_refiner_node(state: GraphState) -> Dict[str, Any]:
    cited_urls = state.get("cited_urls", [])
    cited_sources = state.get("cited_sources", [])
    context = f"""
        History: {[msg.content for msg in state.get("messages", [])]},
        Question: {state.get("question", "")},
        Multi-Agent framework solution plan: {state.get("plan", "")},
        Web Search Status: {state.get("search_status", "")},
        Web Search Error: {state.get("search_error", "")},
        Search Results: {state.get("search_results", "")},
        Scraped Content: {state.get("scraped_content", "")},
        Document Context: {state.get("rag_context", "")},
        cited_urls: {cited_urls}
        cited_sources: {cited_sources}
    """
    answer = answer_refiner_agent.invoke({"context": context})
    logger.info(f"Refined answer: {answer}")
    return {
        "messages": AIMessage(content=answer),
        "plan": "",
        "executed_agents": state.get("executed_agents", []) + ['answer_refiner'],
        "resolved": True,
    }
