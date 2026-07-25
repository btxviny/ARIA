from pathlib import Path
from typing import Any, Dict

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from loguru import logger

from src.agents.agents import orchestrator_agent
from src.agents.state import GraphState
from src.agents.utils import format_history, normalize_pipeline
from src.config import UPLOADS_DIR
from src.rag import vectorstore

_ACCEPTED_DATA_EXTS = {".xlsx", ".xls", ".csv", ".json", ".parquet", ".tsv"}


def _list_data_files(thread_id: str) -> list[dict]:
    thread_dir = Path(UPLOADS_DIR) / thread_id
    if not thread_dir.exists():
        return []
    return [
        {"filename": f.name, "path": str(f)}
        for f in sorted(thread_dir.iterdir())
        if f.is_file() and f.suffix.lower() in _ACCEPTED_DATA_EXTS
    ]


def orchestrator_node(state: GraphState, config: RunnableConfig) -> Dict[str, Any]:
    thread_id = config["configurable"]["thread_id"]
    try:
        sources = vectorstore.list_sources(thread_id)
    except Exception as e:
        logger.warning(f"Orchestrator: failed to check uploaded sources: {e}")
        sources = []
    sources_available = len(sources) > 0
    filenames = [s["filename"] for s in sources]

    data_files = _list_data_files(thread_id)
    data_files_available = len(data_files) > 0
    data_file_names = [f["filename"] for f in data_files]

    context = f"""
        History: {format_history(state.get("messages", []), state.get("summary", ""))},
        Question: {state.get("question", "")}
        Sources available: {sources_available}
        Uploaded source filenames: {filenames}
        Data files available for code analysis: {data_files_available}
        Uploaded data file names: {data_file_names}
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
        "data_files": data_files,
        "executed_agents": state.get("executed_agents", []) + ['orchestrator'],
    }
