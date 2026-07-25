"""RAG source-management routes: upload/list/delete uploaded documents.

This process must never touch `src/rag/vectorstore.py` directly -- it goes
through the Celery tasks in `src/tasks.py`, which run in the worker process
that actually owns the on-disk Chroma store. See `src/rag/vectorstore.py`
for why.
"""
import base64

from fastapi import APIRouter, HTTPException

from src.config import MAX_UPLOAD_MB
from src.schemas import (
    DeleteSourceResponse,
    SourceListResponse,
    SourceUploadRequest,
    SourceUploadResponse,
    SourceUploadTask,
)
from src.tasks import delete_source_task, ingest_source_task, list_sources_task

router = APIRouter(prefix="/sources", tags=["sources"])


@router.post("/upload", response_model=SourceUploadResponse)
def upload_sources(request: SourceUploadRequest) -> SourceUploadResponse:
    """Dispatch one ingestion task per file. Poll each via GET /answer/{task_id}."""
    if not request.files:
        raise HTTPException(status_code=400, detail="files must not be empty")

    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    tasks = []
    for f in request.files:
        try:
            decoded_len = len(base64.b64decode(f.content_base64, validate=True))
        except Exception:
            raise HTTPException(status_code=400, detail=f"'{f.filename}' is not valid base64 content")
        if decoded_len > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"'{f.filename}' exceeds the {MAX_UPLOAD_MB}MB upload limit",
            )
        task = ingest_source_task.apply_async(args=[request.thread_id, f.filename, f.content_base64])
        tasks.append(SourceUploadTask(filename=f.filename, task_id=task.id))

    return SourceUploadResponse(tasks=tasks)


@router.get("/{thread_id}", response_model=SourceListResponse)
def list_sources(thread_id: str) -> SourceListResponse:
    """List uploaded sources for a thread. Fast local read, done synchronously."""
    result = list_sources_task.apply_async(args=[thread_id]).get(timeout=10)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return SourceListResponse(sources=result.get("sources", []))


@router.delete("/{thread_id}/{source_id}", response_model=DeleteSourceResponse)
def delete_source(thread_id: str, source_id: str) -> DeleteSourceResponse:
    """Delete one uploaded source. Fast local write, done synchronously."""
    result = delete_source_task.apply_async(args=[thread_id, source_id]).get(timeout=10)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return DeleteSourceResponse(deleted=result.get("deleted", False))
