from typing import Any, Dict

from langchain_core.messages import AIMessage
from loguru import logger

from src.agents.agents import answer_refiner_agent
from src.agents.state import GraphState
from src.agents.utils import format_history


def answer_refiner_node(state: GraphState) -> Dict[str, Any]:
    cited_urls = state.get("cited_urls", [])
    cited_sources = state.get("cited_sources", [])
    code_result = state.get("code_result", "")
    code_error = state.get("code_error", "")
    code_files = state.get("code_files", [])
    code_run_id = state.get("code_run_id", "")
    code_files_summary = (
        f"Generated files: {[f['filename'] for f in code_files]}" if code_files else ""
    )
    code_error_summary = (
        f"Code Execution Failed (all retries exhausted):\n{code_error}" if code_error else ""
    )

    context = f"""
        History: {format_history(state.get("messages", []), state.get("summary", ""))},
        Question: {state.get("question", "")},
        Multi-Agent framework solution plan: {state.get("plan", "")},
        Web Search Status: {state.get("search_status", "")},
        Web Search Error: {state.get("search_error", "")},
        Search Results: {state.get("search_results", "")},
        Scraped Content: {state.get("scraped_content", "")},
        Document Context: {state.get("rag_context", "")},
        Code Execution Result: {code_result},
        {code_files_summary}
        {code_error_summary}
        cited_urls: {cited_urls}
        cited_sources: {cited_sources}
    """
    answer = answer_refiner_agent.invoke({"context": context})
    logger.info(f"Refined answer: {answer}")
    return {
        "messages": AIMessage(content=answer),
        "plan": "",
        "executed_agents": state.get("executed_agents", []) + ['answer_refiner'],
    }
