from typing import Any, Dict

from langchain_core.runnables import RunnableConfig
from loguru import logger

from src.agents.agents import rag_retriever_agent
from src.agents.state import GraphState
from src.agents.utils import dedup_urls, format_history
from src.config import RAG_MAX_CONTEXT_CHARS, RAG_TOP_K
from src.rag import vectorstore

from src.agents.nodes._common import NO_RAG_RESULTS


def rag_retriever_node(state: GraphState, config: RunnableConfig) -> Dict[str, Any]:
    """Formulates a retrieval query and searches the thread's uploaded personal sources."""
    thread_id = config["configurable"]["thread_id"]
    question = state.get("question", "")
    plan = state.get("plan", "")
    history = format_history(state.get("messages", []))

    try:
        query = rag_retriever_agent.invoke({"question": question, "plan": plan, "history": history})
    except Exception as e:
        logger.warning(f"RAG Retriever query formulation failed, falling back to raw question: {e}")
        query = question

    try:
        chunks = vectorstore.query(thread_id, query, k=RAG_TOP_K)
    except Exception as e:
        logger.error(f"RAG Retriever query against vector store failed: {e}")
        chunks = []

    blocks = []
    filenames = []
    total_chars = 0
    for chunk in chunks:
        header = f"Source: {chunk['filename']}"
        if chunk.get("page"):
            header += f" (page {chunk['page']})"
        block = f"{header}\nContent:\n{chunk['content']}"
        if total_chars + len(block) > RAG_MAX_CONTEXT_CHARS:
            remaining = RAG_MAX_CONTEXT_CHARS - total_chars
            if remaining > 0:
                blocks.append(block[:remaining] + "\n...[truncated]")
            break
        blocks.append(block)
        total_chars += len(block)
        filenames.append(chunk["filename"])

    rag_context = "\n---\n".join(blocks) if blocks else NO_RAG_RESULTS
    logger.info(f"RAG Retriever found {len(chunks)} chunks for thread_id={thread_id}")

    return {
        "rag_context": rag_context,
        "cited_sources": dedup_urls(state.get("cited_sources", []) + filenames),
        "executed_agents": state.get("executed_agents", []) + ['rag_retriever'],
    }
