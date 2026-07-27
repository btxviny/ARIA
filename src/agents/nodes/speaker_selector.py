from langgraph.graph import END
from langgraph.types import Command
from loguru import logger

from src.agents.agents import supervisor_agent
from src.agents.nodes._common import NO_RAG_RESULTS, NO_SCRAPED_CONTENT, NO_SEARCH_RESULTS
from src.agents.nodes.code_executor import MAX_SUPERVISOR_RETRIES
from src.agents.state import GraphState
from src.agents.utils import VALID_PIPELINE_AGENTS

_RESEARCH_TRIGGERS = {"web_searcher", "web_scraper", "rag_retriever"}


def _needs_research_analyst(executed: list[str]) -> bool:
    """Return True if a data-gathering agent ran but research_analyst hasn't yet."""
    return (
        any(a in _RESEARCH_TRIGGERS for a in executed)
        and "research_analyst" not in executed
        and "code_executor" not in executed
    )


def _summarise_state(state: GraphState) -> str:
    """Build a human-readable summary of what each completed agent produced."""
    lines = []

    search_status = state.get("search_status", "")
    search_results = state.get("search_results", NO_SEARCH_RESULTS)
    if search_status:
        if search_status == "ok":
            preview = (search_results[:300] + "…") if len(search_results) > 300 else search_results
            lines.append(f"web_searcher: succeeded. Results preview: {preview}")
        else:
            lines.append(f"web_searcher: {search_status}. Error: {state.get('search_error', '')}")

    scraped = state.get("scraped_content", NO_SCRAPED_CONTENT)
    if scraped and scraped != NO_SCRAPED_CONTENT:
        preview = (scraped[:300] + "…") if len(scraped) > 300 else scraped
        lines.append(f"web_scraper: succeeded. Content preview: {preview}")
    elif "web_scraper" in state.get("executed_agents", []):
        lines.append("web_scraper: ran but extracted no content.")

    rag = state.get("rag_context", NO_RAG_RESULTS)
    if rag and rag != NO_RAG_RESULTS:
        preview = (rag[:300] + "…") if len(rag) > 300 else rag
        lines.append(f"rag_retriever: found relevant content. Preview: {preview}")
    elif "rag_retriever" in state.get("executed_agents", []):
        lines.append("rag_retriever: ran but found no relevant content.")

    code_result = state.get("code_result", "")
    code_error = state.get("code_error", "")
    if code_result:
        lines.append(f"code_executor: {'failed after all retries. Last error: ' + code_error if code_error else 'succeeded. Output: ' + code_result[:200]}")
    elif "code_executor" in state.get("executed_agents", []):
        lines.append("code_executor: ran with no output.")

    if "research_analyst" in state.get("executed_agents", []):
        lines.append("research_analyst: completed synthesis.")

    return "\n".join(lines) if lines else "No agents have produced output yet."


def speaker_selector_node(state: GraphState) -> Command:
    # Terminal: answer has been written
    if state.get("resolved", False):
        logger.debug("Answer already refined, terminating.")
        return Command(goto=END, update={"next": END, "resolved": False})

    pipeline = state.get("pipeline", []) or []
    executed = state.get("executed_agents", [])
    remaining = [a for a in pipeline if a not in executed]

    # Hard rules: code retry / exhaustion
    if state.get("code_error"):
        attempt = state.get("code_attempt", 0)
        if attempt < MAX_SUPERVISOR_RETRIES:
            logger.info("Code failed (attempt %d/%d) — retrying code_executor.", attempt, MAX_SUPERVISOR_RETRIES)
            return Command(goto="code_executor", update={"next": "code_executor"})
        else:
            logger.info("Code failed after %d attempts — routing to answer_refiner.", MAX_SUPERVISOR_RETRIES)
            return Command(goto="answer_refiner", update={"next": "answer_refiner"})

    # Build context for the LLM supervisor
    no_search = state.get("search_results", NO_SEARCH_RESULTS) == NO_SEARCH_RESULTS
    no_scrape = state.get("scraped_content", NO_SCRAPED_CONTENT) == NO_SCRAPED_CONTENT
    no_rag = state.get("rag_context", NO_RAG_RESULTS) == NO_RAG_RESULTS

    context = (
        f"User's question: {state.get('question', '')}\n\n"
        f"Orchestrator's suggested pipeline: {pipeline}\n"
        f"Agents already executed: {executed}\n"
        f"Remaining suggested agents: {remaining}\n\n"
        f"Agent outputs so far:\n{_summarise_state(state)}\n\n"
        f"Data availability: "
        f"search_results={'empty' if no_search else 'available'}, "
        f"search_status={state.get('search_status', 'not run')}, "
        f"scraped_content={'empty' if no_scrape else 'available'}, "
        f"rag_context={'empty' if no_rag else 'available'}"
    )

    speaker = None
    try:
        result = supervisor_agent.invoke({"context": context})
        if result and result.speaker:
            speaker = result.speaker
            logger.info(f"Supervisor decided: {speaker} — {result.reasoning}")
    except Exception as e:
        logger.warning("Supervisor LLM failed: %s — falling back to suggested pipeline.", e)

    # Fallback: if LLM failed or returned something invalid, use remaining[0]
    valid_agents = VALID_PIPELINE_AGENTS | {"END"}
    if speaker not in valid_agents or speaker in executed:
        speaker = remaining[0] if remaining else "answer_refiner"
        logger.warning("Supervisor fallback → %s", speaker)

    if speaker == "END":
        return Command(goto=END, update={"next": END, "resolved": False})

    # Guard: never skip research_analyst when data agents ran without code_executor
    if speaker == "answer_refiner" and _needs_research_analyst(executed):
        logger.info("Invariant: routing to research_analyst before answer_refiner.")
        return Command(goto="research_analyst", update={"next": "research_analyst"})

    return Command(goto=speaker, update={"next": speaker})
