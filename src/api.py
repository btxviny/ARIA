"""FastAPI layer: accepts chat questions, dispatches them to Celery, and
exposes endpoints for polling the answer."""
import sys
from typing import Optional

from celery.result import AsyncResult
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.banner import BANNER
from src.tasks import app as celery_app, process_chat_task

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

app = FastAPI(title="Multi-Agent Chatbot API", version="1.0.0")

print(BANNER)


class ChatRequest(BaseModel):
    prompt: str
    thread_id: Optional[str] = None


class ChatResponse(BaseModel):
    task_id: str


class AnswerResponse(BaseModel):
    status: str  # "Pending" | "Completed" | "Failed"
    result: Optional[dict] = None
    error: Optional[str] = None


@app.get("/health")
def health() -> dict:
    """Simple liveness check."""
    return {"status": "ok"}


@app.post("/question/", response_model=ChatResponse)
def question(request: ChatRequest) -> ChatResponse:
    """Dispatch the question to Celery and return the task id for polling."""
    if not request.prompt or not request.prompt.strip():
        raise HTTPException(status_code=400, detail="prompt must not be empty")

    thread_id = request.thread_id or "default"
    task = process_chat_task.apply_async(args=[request.prompt, thread_id])
    return ChatResponse(task_id=task.id)


@app.get("/answer/{task_id}", response_model=AnswerResponse)
def answer(task_id: str) -> AnswerResponse:
    """Poll for the task result. Returns one of Pending / Completed / Failed."""
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
