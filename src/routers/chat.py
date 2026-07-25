"""Chat routes: dispatch a question to Celery and poll for the answer."""
from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException

from src.schemas import AnswerResponse, ChatRequest, ChatResponse
from src.tasks import app as celery_app, process_chat_task

router = APIRouter(tags=["chat"])


@router.post("/question/", response_model=ChatResponse)
def question(request: ChatRequest) -> ChatResponse:
    """Dispatch the question to Celery and return the task id for polling."""
    if not request.prompt or not request.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt must not be empty")

    thread_id = request.thread_id or "default"
    task = process_chat_task.apply_async(args=[request.prompt, thread_id])
    return ChatResponse(task_id=task.id)


@router.get("/answer/{task_id}", response_model=AnswerResponse)
def answer(task_id: str) -> AnswerResponse:
    """Poll for a task result. Returns one of Pending / Completed / Failed.

    Generic over any Celery task id -- reused for both `process_chat_task`
    (chat turns) and `ingest_source_task` (source uploads), since both
    return a plain dict and this endpoint just passes it through.
    """
    result = AsyncResult(task_id, app=celery_app)
    state = result.state

    if state in ("PENDING", "STARTED", "RETRY"):
        return AnswerResponse(status="Pending")

    if state == "SUCCESS":
        payload = result.result
        if isinstance(payload, dict) and "error" in payload and "answer" not in payload:
            # Task completed but the agent itself reported an error.
            return AnswerResponse(status="Failed", error=str(payload["error"]))
        return AnswerResponse(status="Completed", result=payload)

    # FAILURE / REVOKED / any unexpected state.
    error_msg = str(result.result) if result.result else f"Task ended in state {state}"
    return AnswerResponse(status="Failed", error=error_msg)
