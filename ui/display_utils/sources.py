"""Unified file upload panel.

- PDF / TXT / MD  → ingested into Chroma for RAG (Celery task, polled)
- XLSX / XLS / CSV / JSON / PARQUET / TSV → saved as raw data files for the code executor

Public entry points:
  render_file_strip(thread_id)  — sidebar uploader/manager + file chips above the chat input
"""
import base64
import time

import requests
import streamlit as st

from src.config import API_BASE_URL, RESPONSE_POLL_INTERVAL, SOURCE_INGEST_TIMEOUT_SECONDS

RAG_TYPES = {"pdf", "txt", "md"}
DATA_TYPES = {"xlsx", "xls", "csv", "json", "parquet", "tsv"}
ALL_TYPES = sorted(RAG_TYPES | DATA_TYPES)


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------

def _ingest_rag_files(thread_id: str, files) -> list[dict]:
    payload = {
        "thread_id": thread_id,
        "files": [
            {"filename": f.name, "content_base64": base64.b64encode(f.getvalue()).decode("ascii")}
            for f in files
        ],
    }
    r = requests.post(f"{API_BASE_URL}/sources/upload", json=payload, timeout=30)
    r.raise_for_status()
    return r.json().get("tasks", [])


def _upload_data_files(thread_id: str, files) -> None:
    payload = {
        "thread_id": thread_id,
        "files": [
            {"filename": f.name, "content_base64": base64.b64encode(f.getvalue()).decode("ascii")}
            for f in files
        ],
    }
    r = requests.post(f"{API_BASE_URL}/datafiles/upload", json=payload, timeout=30)
    r.raise_for_status()


def _fetch_rag_sources(thread_id: str) -> list[dict]:
    try:
        r = requests.get(f"{API_BASE_URL}/sources/{thread_id}", timeout=10)
        r.raise_for_status()
        return r.json().get("sources", [])
    except requests.RequestException as e:
        st.error(f"Failed to load sources: {e}")
        return []


def _fetch_data_files(thread_id: str) -> list[dict]:
    try:
        r = requests.get(f"{API_BASE_URL}/datafiles/{thread_id}", timeout=10)
        r.raise_for_status()
        return r.json().get("files", [])
    except requests.RequestException as e:
        st.error(f"Failed to load data files: {e}")
        return []


def _delete_rag_source(thread_id: str, source_id: str) -> None:
    try:
        r = requests.delete(f"{API_BASE_URL}/sources/{thread_id}/{source_id}", timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        st.error(f"Failed to delete source: {e}")


def _delete_data_file(thread_id: str, filename: str) -> None:
    try:
        r = requests.delete(f"{API_BASE_URL}/datafiles/{thread_id}/{filename}", timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        st.error(f"Failed to delete {filename}: {e}")


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

def _init_state() -> None:
    for key, default in [
        ("uploaded_signatures", set()),
        ("pending_ingest_tasks", []),
        ("sources_cache", {}),
        ("data_files_cache", {}),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default


def _invalidate_rag(thread_id: str) -> None:
    st.session_state.sources_cache.pop(thread_id, None)


def _invalidate_data(thread_id: str) -> None:
    st.session_state.data_files_cache.pop(thread_id, None)


def _get_rag_sources(thread_id: str) -> list[dict]:
    if thread_id not in st.session_state.sources_cache:
        st.session_state.sources_cache[thread_id] = _fetch_rag_sources(thread_id)
    return st.session_state.sources_cache[thread_id]


def _get_data_files(thread_id: str) -> list[dict]:
    if thread_id not in st.session_state.data_files_cache:
        st.session_state.data_files_cache[thread_id] = _fetch_data_files(thread_id)
    return st.session_state.data_files_cache[thread_id]


# ---------------------------------------------------------------------------
# RAG polling fragment
# ---------------------------------------------------------------------------

@st.fragment(run_every=RESPONSE_POLL_INTERVAL)
def _poll_pending_ingests(thread_id: str) -> None:
    if not st.session_state.pending_ingest_tasks:
        return

    still_pending = []
    any_finished = False
    for task in st.session_state.pending_ingest_tasks:
        if time.time() - task["started_at"] > SOURCE_INGEST_TIMEOUT_SECONDS:
            st.error(f"'{task['filename']}': ingestion timed out")
            any_finished = True
            continue
        try:
            r = requests.get(f"{API_BASE_URL}/answer/{task['task_id']}", timeout=10)
            r.raise_for_status()
            result = r.json()
        except requests.RequestException:
            still_pending.append(task)
            continue

        status = result.get("status")
        if status == "Completed":
            any_finished = True
        elif status == "Failed":
            st.error(f"'{task['filename']}': {result.get('error', 'Unknown error')}")
            any_finished = True
        else:
            still_pending.append(task)

    st.session_state.pending_ingest_tasks = still_pending
    if any_finished:
        _invalidate_rag(thread_id)
    if still_pending:
        st.caption(f"Indexing {len(still_pending)} file(s)...")
    if any_finished and not still_pending:
        st.rerun()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / 1024 / 1024:.1f} MB"


def _handle_new_uploads(thread_id: str, uploaded_files) -> bool:
    """Process newly uploaded files. Returns True if any upload was processed."""
    new_files = [
        f for f in (uploaded_files or [])
        if f.file_id not in st.session_state.uploaded_signatures
    ]
    if not new_files:
        return False

    for f in new_files:
        st.session_state.uploaded_signatures.add(f.file_id)

    rag_files = [f for f in new_files if f.name.rsplit(".", 1)[-1].lower() in RAG_TYPES]
    data_files = [f for f in new_files if f.name.rsplit(".", 1)[-1].lower() in DATA_TYPES]

    if rag_files:
        try:
            tasks = _ingest_rag_files(thread_id, rag_files)
            now = time.time()
            for t in tasks:
                st.session_state.pending_ingest_tasks.append(
                    {"filename": t["filename"], "task_id": t["task_id"], "started_at": now}
                )
        except requests.RequestException as e:
            st.error(f"RAG upload failed: {e}")

    if data_files:
        try:
            _upload_data_files(thread_id, data_files)
            _invalidate_data(thread_id)
        except requests.RequestException as e:
            st.error(f"Data file upload failed: {e}")

    return True


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def render_file_strip(thread_id: str) -> None:
    """Sidebar uploader + manage panel; file chips rendered above the chat input."""
    _init_state()

    # --- Sidebar: uploader + file list (reliable — avoids st.popover/file_uploader issues) ---
    with st.sidebar:
        st.divider()
        st.markdown("**Files**")
        st.caption("PDF / TXT / MD → RAG  ·  CSV / Excel / JSON / Parquet → code analysis")

        uploaded = st.file_uploader(
            "Upload files",
            type=ALL_TYPES,
            accept_multiple_files=True,
            key="source_uploader",
            label_visibility="collapsed",
        )
        if _handle_new_uploads(thread_id, uploaded):
            st.rerun()

        rag_sources = _get_rag_sources(thread_id)
        data_file_list = _get_data_files(thread_id)

        for s in rag_sources:
            c1, c2 = st.columns([5, 1])
            c1.caption(f"📄 {s['filename']} ({s['num_chunks']} chunks)")
            if c2.button("🗑", key=f"del_rag_{s['source_id']}", help="Delete"):
                _delete_rag_source(thread_id, s["source_id"])
                _invalidate_rag(thread_id)
                st.rerun()
        for f in data_file_list:
            c1, c2 = st.columns([5, 1])
            c1.caption(f"📊 {f['filename']} ({_fmt_size(f['size_bytes'])})")
            if c2.button("🗑", key=f"del_df_{f['filename']}", help="Delete"):
                _delete_data_file(thread_id, f["filename"])
                _invalidate_data(thread_id)
                st.rerun()

        if not rag_sources and not data_file_list:
            st.caption("No files uploaded yet.")

    # --- Main area: polling + file chips ---
    rag_sources = _get_rag_sources(thread_id)
    data_file_list = _get_data_files(thread_id)

    if st.session_state.pending_ingest_tasks:
        _poll_pending_ingests(thread_id)

    all_names = (
        [f"📄 {s['filename']}" for s in rag_sources]
        + [f"📊 {f['filename']}" for f in data_file_list]
    )
    if all_names:
        chips_html = "".join(
            f'<span class="file-chip">{name}</span>' for name in all_names
        )
        st.markdown(f'<div class="file-strip">{chips_html}</div>', unsafe_allow_html=True)
    elif not st.session_state.pending_ingest_tasks:
        st.markdown(
            '<div class="file-strip"><span class="file-chip-empty">No files attached · upload via sidebar</span></div>',
            unsafe_allow_html=True,
        )
