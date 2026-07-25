"""Sidebar "Sources" UI: upload, list, and delete personal RAG sources.

Talks only to the FastAPI layer (upload -> Celery-dispatched + polled via the
existing /answer/{task_id} endpoint, list/delete -> synchronous). Never
touches the vector store directly -- see `src/rag/vectorstore.py`.
"""
import base64
import time

import requests
import streamlit as st

from src.config import API_BASE_URL, RESPONSE_POLL_INTERVAL, SOURCE_INGEST_TIMEOUT_SECONDS

ACCEPTED_TYPES = ["pdf", "txt", "md"]


def _upload_files(thread_id: str, files) -> list[dict]:
    payload = {
        "thread_id": thread_id,
        "files": [
            {
                "filename": f.name,
                "content_base64": base64.b64encode(f.getvalue()).decode("ascii"),
            }
            for f in files
        ],
    }
    r = requests.post(f"{API_BASE_URL}/sources/upload", json=payload, timeout=30)
    r.raise_for_status()
    return r.json().get("tasks", [])


def _fetch_sources(thread_id: str) -> list[dict]:
    try:
        r = requests.get(f"{API_BASE_URL}/sources/{thread_id}", timeout=10)
        r.raise_for_status()
        return r.json().get("sources", [])
    except requests.RequestException as e:
        st.error(f"Failed to load sources: {e}")
        return []


def _delete_source(thread_id: str, source_id: str) -> None:
    try:
        r = requests.delete(f"{API_BASE_URL}/sources/{thread_id}/{source_id}", timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        st.error(f"Failed to delete source: {e}")


def _init_state() -> None:
    if "uploaded_signatures" not in st.session_state:
        st.session_state.uploaded_signatures = set()
    if "pending_ingest_tasks" not in st.session_state:
        st.session_state.pending_ingest_tasks = []  # [{filename, task_id, started_at}]
    if "sources_cache" not in st.session_state:
        st.session_state.sources_cache = {}  # thread_id -> list[source dict]


def _get_cached_sources(thread_id: str) -> list[dict]:
    # Fetched at most once per thread per cache invalidation, instead of on
    # every single Streamlit rerun (any button click anywhere in the app).
    if thread_id not in st.session_state.sources_cache:
        st.session_state.sources_cache[thread_id] = _fetch_sources(thread_id)
    return st.session_state.sources_cache[thread_id]


def _invalidate_sources(thread_id: str) -> None:
    st.session_state.sources_cache.pop(thread_id, None)


@st.fragment(run_every=RESPONSE_POLL_INTERVAL)
def _poll_pending_ingests(thread_id: str) -> None:
    """Poll in-flight ingestion tasks one tick at a time. Only this fragment
    reruns every tick -- not the whole page -- so the UI stays responsive
    while a file is being indexed."""
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
        _invalidate_sources(thread_id)
    if still_pending:
        st.caption(f"Indexing {len(still_pending)} file(s)...")
    if any_finished and not still_pending:
        st.rerun()


def render_sources_sidebar(thread_id: str) -> None:
    """Render the upload widget + source list for the current conversation."""
    _init_state()
    st.markdown("**Sources**")
    st.caption("Upload PDF/TXT/MD files for the agents to answer from.")

    uploaded_files = st.file_uploader(
        "Upload sources",
        type=ACCEPTED_TYPES,
        accept_multiple_files=True,
        key="source_uploader",
        label_visibility="collapsed",
    )

    # Streamlit reruns on every interaction and the uploader retains its
    # selection, so only dispatch files we haven't already sent for ingest.
    new_files = [
        f for f in (uploaded_files or [])
        if f.file_id not in st.session_state.uploaded_signatures
    ]
    if new_files:
        for f in new_files:
            st.session_state.uploaded_signatures.add(f.file_id)
        try:
            tasks = _upload_files(thread_id, new_files)
        except requests.RequestException as e:
            st.error(f"Upload failed: {e}")
            tasks = []
        now = time.time()
        for t in tasks:
            st.session_state.pending_ingest_tasks.append(
                {"filename": t["filename"], "task_id": t["task_id"], "started_at": now}
            )

    if st.session_state.pending_ingest_tasks:
        _poll_pending_ingests(thread_id)

    sources = _get_cached_sources(thread_id)
    if not sources:
        st.caption("No sources uploaded yet.")
        return

    for s in sources:
        col1, col2 = st.columns([5, 1])
        with col1:
            st.caption(f"\U0001F4C4 {s['filename']} ({s['num_chunks']} chunks)")
        with col2:
            if st.button("\U0001F5D1", key=f"del_{s['source_id']}", help="Delete this source"):
                _delete_source(thread_id, s["source_id"])
                _invalidate_sources(thread_id)
                st.rerun()
