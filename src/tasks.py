"""Celery tasks that wrap the multi-agent graph and the RAG source store.

The RAG source-management tasks (`ingest_source_task`, `list_sources_task`,
`delete_source_task`) are the ONLY way FastAPI (`src/api.py`) may touch the
vector store -- it runs in a separate process from this worker and must not
open the on-disk Chroma store directly. See `src/rag/vectorstore.py` for why.
"""
import base64
import uuid

from celery import Celery
from loguru import logger

from src.agents.graph import app as agent_graph
from src.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND, MAX_UPLOAD_MB
from src.db import session_service
from src.rag import ingest, vectorstore

app = Celery(
    "multiagent_chatbot",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

try:
    session_service.init_schema()
except Exception:
    pass  # POSTGRES_URL not set or DB unreachable on worker start; logged inside init_schema


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
        config = {"configurable": {"thread_id": thread_id}}
        inputs = {
            "question": prompt,
            "executed_agents": [],
            "pipeline": [],
            "plan": "",
            "code_run_id": "",
            "code_files": [],
            "code_result": "",
            "code_error": "",
            "data_files": [],
        }
        event = None
        for event in agent_graph.stream(inputs, config, stream_mode="values"):
            pass
        if event is None:
            return {"error": "Graph produced no output", "thread_id": thread_id}
        logger.info(f"[thread_id={thread_id}] Final state keys: {list(event.keys())}")
        messages = event.get("messages", [])
        final_answer = messages[-1].content if messages else ""
        logger.success(f"[thread_id={thread_id}] Final response: {final_answer[:200]}...")
        reply = {
            "answer": final_answer,
            "code_files": event.get("code_files", []),
            "code_run_id": event.get("code_run_id", ""),
            "code_result": event.get("code_result", ""),
            "web_result_cards": event.get("web_result_cards", []),
        }
    except Exception as e:
        logger.exception(f"process_chat_task failed for thread_id={thread_id}")
        return {"error": str(e), "thread_id": thread_id}

    result = {
        "answer": reply.get("answer", ""),
        "thread_id": thread_id,
        "code_files": reply.get("code_files", []),
        "code_run_id": reply.get("code_run_id", ""),
        "code_result": reply.get("code_result", ""),
        "web_result_cards": reply.get("web_result_cards", []),
    }

    # Persist both messages — best-effort; a DB error must never fail the task.
    try:
        existing = session_service.count_messages(thread_id)
        # The session row must exist first: `messages.thread_id` has an FK
        # to `sessions.thread_id`, so upserting after save_message() would
        # violate that constraint on every first message of a new thread.
        # Title is derived from the first user message; subsequent calls pass
        # an empty string so the UPSERT SQL keeps the original title.
        candidate_title = prompt[:80] if existing == 0 else ""
        session_service.upsert_session(
            thread_id=thread_id,
            title=candidate_title,
            message_count=existing + 2,
        )
        session_service.save_message(
            thread_id=thread_id,
            role="user",
            content=prompt,
            code_run_id=None,
            code_files=None,
            code_result=None,
            message_index=existing,
        )
        session_service.save_message(
            thread_id=thread_id,
            role="assistant",
            content=result["answer"],
            code_run_id=result["code_run_id"] or None,
            code_files=result["code_files"] or None,
            code_result=result["code_result"] or None,
            web_result_cards=result["web_result_cards"] or None,
            message_index=existing + 1,
        )
    except Exception as db_err:
        logger.warning(f"Failed to persist session for thread_id={thread_id}: {db_err}")

    return result


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
