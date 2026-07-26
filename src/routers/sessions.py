"""Session history routes: list past conversations and retrieve their messages."""
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from src.db import session_service
from src.schemas import MessageInfo, SessionInfo

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


@router.get("/{thread_id}/messages", response_model=list[MessageInfo])
def get_messages(thread_id: str) -> list[MessageInfo]:
    """Return all messages for a thread ordered by message_index."""
    try:
        return session_service.get_messages(thread_id)
    except Exception as e:
        logger.exception(f"get_messages failed for thread_id={thread_id}")
        raise HTTPException(status_code=500, detail=str(e))
