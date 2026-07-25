"""Celery tasks that wrap the multi-agent graph and the RAG source store.

A single `CIAgent` instance is shared across tasks (the LangGraph app is
stateless; per-conversation memory lives in the graph checkpointer keyed by
`thread_id`).

The RAG source-management tasks (`ingest_source_task`, `list_sources_task`,
`delete_source_task`) are the ONLY way FastAPI (`src/api.py`) may touch the
vector store -- it runs in a separate process from this worker and must not
open the on-disk Chroma store directly. See `src/rag/vectorstore.py` for why.
"""
import base64
import uuid

from celery import Celery
from loguru import logger

from src.agents.ci_agent import CIAgent
from src.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, MAX_UPLOAD_MB
from src.rag import ingest, vectorstore

app = Celery(
    "multiagent_chatbot",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

ci_agent = CIAgent()


@app.task
def process_chat_task(prompt: str, thread_id: str = "default") -> dict:
    """Run the agent graph for a single user turn.

    Parameters
    ----------
    prompt : str
        The user's question.
    thread_id : str
        Identifier for the conversation memory. Each UI session should pass
        its own id so separate chats do not share history.
    """
    try:
        reply = ci_agent.generate_reply(query=prompt, thread_id=thread_id)
        return {
            "answer": reply.get("answer", ""),
            "thread_id": thread_id,
            "code_files": reply.get("code_files", []),
            "code_run_id": reply.get("code_run_id", ""),
            "code_result": reply.get("code_result", ""),
        }
    except Exception as e:
        logger.exception(f"process_chat_task failed for thread_id={thread_id}")
        return {"error": str(e), "thread_id": thread_id}


@app.task
def ingest_source_task(thread_id: str, filename: str, content_base64: str) -> dict:
    """Parse, chunk, and embed one uploaded source file into the thread's collection."""
    try:
        raw_bytes = base64.b64decode(content_base64)
    except Exception as e:
        return {"error": f"Could not decode uploaded file: {e}", "thread_id": thread_id, "filename": filename}

    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    if len(raw_bytes) > max_bytes:
        return {
            "error": f"File '{filename}' exceeds the {MAX_UPLOAD_MB}MB upload limit.",
            "thread_id": thread_id,
            "filename": filename,
        }

    try:
        source_id = str(uuid.uuid4())
        chunks = ingest.load_and_chunk(raw_bytes, filename, source_id)
        num_chunks = vectorstore.add_documents(thread_id, source_id, chunks)
        logger.info(f"Ingested '{filename}' for thread_id={thread_id}: {num_chunks} chunks")
        return {
            "source_id": source_id,
            "filename": filename,
            "num_chunks": num_chunks,
            "thread_id": thread_id,
        }
    except Exception as e:
        logger.exception(f"ingest_source_task failed for thread_id={thread_id}, filename={filename}")
        return {"error": str(e), "thread_id": thread_id, "filename": filename}


@app.task
def list_sources_task(thread_id: str) -> dict:
    """List uploaded sources for a thread."""
    try:
        sources = vectorstore.list_sources(thread_id)
        return {"sources": sources, "thread_id": thread_id}
    except Exception as e:
        logger.exception(f"list_sources_task failed for thread_id={thread_id}")
        return {"error": str(e), "thread_id": thread_id}


@app.task
def delete_source_task(thread_id: str, source_id: str) -> dict:
    """Delete one uploaded source from a thread's collection."""
    try:
        deleted = vectorstore.delete_source(thread_id, source_id)
        return {"deleted": deleted, "thread_id": thread_id, "source_id": source_id}
    except Exception as e:
        logger.exception(f"delete_source_task failed for thread_id={thread_id}, source_id={source_id}")
        return {"error": str(e), "thread_id": thread_id, "source_id": source_id}
