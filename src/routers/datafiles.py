"""Data file upload routes: save raw files (Excel, CSV, JSON…) for code executor analysis."""
import base64
from pathlib import Path

from fastapi import APIRouter, HTTPException

from src.config import MAX_UPLOAD_MB, UPLOADS_DIR
from src.schemas import (
    DataFileInfo,
    DataFilesListResponse,
    DataFileUploadRequest,
    DeleteDataFileResponse,
)

router = APIRouter(prefix="/datafiles", tags=["datafiles"])

ACCEPTED_EXTENSIONS = {".xlsx", ".xls", ".csv", ".json", ".parquet", ".tsv"}


def _thread_dir(thread_id: str) -> Path:
    d = Path(UPLOADS_DIR) / Path(thread_id).name
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.post("/upload", response_model=DataFilesListResponse)
def upload_data_files(request: DataFileUploadRequest) -> DataFilesListResponse:
    if not request.files:
        raise HTTPException(status_code=400, detail="files must not be empty")

    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    saved: list[DataFileInfo] = []
    thread_dir = _thread_dir(request.thread_id)

    for f in request.files:
        ext = Path(f.filename).suffix.lower()
        if ext not in ACCEPTED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"'{f.filename}': unsupported type. Accepted: {', '.join(sorted(ACCEPTED_EXTENSIONS))}",
            )
        try:
            raw_bytes = base64.b64decode(f.content_base64)
        except Exception:
            raise HTTPException(status_code=400, detail=f"'{f.filename}' is not valid base64")
        if len(raw_bytes) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"'{f.filename}' exceeds the {MAX_UPLOAD_MB} MB upload limit",
            )

        safe_name = Path(f.filename).name
        (thread_dir / safe_name).write_bytes(raw_bytes)
        saved.append(DataFileInfo(filename=safe_name, size_bytes=len(raw_bytes)))

    return DataFilesListResponse(files=saved)


@router.get("/{thread_id}", response_model=DataFilesListResponse)
def list_data_files(thread_id: str) -> DataFilesListResponse:
    thread_dir = Path(UPLOADS_DIR) / Path(thread_id).name
    if not thread_dir.exists():
        return DataFilesListResponse(files=[])
    files = [
        DataFileInfo(filename=f.name, size_bytes=f.stat().st_size)
        for f in sorted(thread_dir.iterdir())
        if f.is_file() and f.suffix.lower() in ACCEPTED_EXTENSIONS
    ]
    return DataFilesListResponse(files=files)


@router.delete("/{thread_id}/{filename}", response_model=DeleteDataFileResponse)
def delete_data_file(thread_id: str, filename: str) -> DeleteDataFileResponse:
    safe_name = Path(filename).name
    file_path = Path(UPLOADS_DIR) / Path(thread_id).name / safe_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    file_path.unlink()
    return DeleteDataFileResponse(deleted=True)
