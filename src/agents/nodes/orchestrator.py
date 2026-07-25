from typing import Any, Dict

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from loguru import logger

from src.agents.agents import orchestrator_agent
from src.agents.state import GraphState
from src.agents.utils import format_history, normalize_pipeline
from src.rag import vectorstore


def orchestrator_node(state: GraphState, config: RunnableConfig) -> Dict[str, Any]:
    thread_id = config["configurable"]["thread_id"]
    try:
        sources = vectorstore.list_sources(thread_id)
    except Exception as e:
        logger.warning(f"Orchestrator: failed to check uploaded sources: {e}")
        sources = []
    sources_available = len(sources) > 0
    filenames = [s["filename"] for s in sources]

    context = f"""
        History: {format_history(state.get("messages", []))},
        Question: {state.get("question", "")}
        Sources available: {sources_available}
        Uploaded source filenames: {filenames}
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

    pipeline = normalize_pipeline(pipeline)
    plan_text = f"{reasoning}\nPipeline: {' -> '.join(pipeline)}"

    logger.warning(f"Orchestrator plan: {plan_text}")
    return {
        "messages": [HumanMessage(content=state.get("question", ""))],
        "plan": plan_text,
        "pipeline": pipeline,
        "executed_agents": state.get("executed_agents", []) + ['orchestrator'],
    }
