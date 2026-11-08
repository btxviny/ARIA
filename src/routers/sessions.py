"""Session history routes: list past conversations and retrieve their messages."""
import shutil
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Response
from loguru import logger

from src.config import CODE_OUTPUTS_DIR, UPLOADS_DIR
from src.db import session_service
from src.schemas import MessageInfo, SessionInfo
from src.tasks import delete_thread_data_task

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionInfo])
def list_sessions(
    limit: int = Query(50, ge=1, le=1000, description="Max sessions to return, most-recently-updated first."),
) -> list[SessionInfo]:
    """Return up to `limit` most-recently-updated sessions."""
    try:
        return session_service.list_sessions(limit=limit)
    except Exception as e:
        logger.exception("list_sessions failed")
        raise HTTPException(status_code=500, detail=str(e))


def _rmtree_child(base: str, name: str) -> None:
    """Remove base/<name>, refusing anything that is not a plain child directory name."""
    child = Path(name).name
    if child in ("", ".", ".."):
        return
    shutil.rmtree(Path(base) / child, ignore_errors=True)


@router.delete("/{thread_id}", status_code=204)
def delete_session(thread_id: str) -> Response:
    """Permanently delete a session and everything stored for it.

    Order matters: the worker-side cleanup (Chroma, agent memory) runs first and
    the DB rows go last, so a failure leaves the chat visible and the delete retryable.
    Removes: messages, uploaded data files, the RAG collection, and code-executor outputs.
    """
    try:
        run_ids = session_service.get_run_ids(thread_id)
        result = delete_thread_data_task.apply_async(args=[thread_id]).get(timeout=15)
        if "error" in result:
            raise RuntimeError(result["error"])
        _rmtree_child(UPLOADS_DIR, thread_id)
        for run_id in run_ids:
            _rmtree_child(CODE_OUTPUTS_DIR, run_id)
        session_service.delete_session(thread_id)
        return Response(status_code=204)
    except Exception as e:
        logger.exception(f"delete_session failed for thread_id={thread_id}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{thread_id}/messages", response_model=list[MessageInfo])
def get_messages(thread_id: str) -> list[MessageInfo]:
    """Return all messages for a thread ordered by message_index."""
    try:
        return session_service.get_messages(thread_id)
    except Exception as e:
        logger.exception(f"get_messages failed for thread_id={thread_id}")
        raise HTTPException(status_code=500, detail=str(e))
