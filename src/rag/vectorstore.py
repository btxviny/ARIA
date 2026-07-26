"""Chroma-backed vector store for personal (per-thread) uploaded sources.

Only `src/tasks.py` (Celery tasks) and `src/agents/nodes.py` (graph nodes,
which execute inside the Celery worker process) should import this module.
FastAPI (`src/api.py`) must never touch it directly -- it is a separate OS
process from the worker, and Chroma's `PersistentClient` is a single-writer,
SQLite-backed embedded store not meant to be opened concurrently from
multiple processes. FastAPI goes through the Celery tasks in `src/tasks.py`
instead.

One Chroma collection per `thread_id` gives isolation-by-construction: a
question asked in one conversation can never retrieve another conversation's
uploaded documents, and "New conversation" (which mints a fresh thread_id)
starts with zero sources for free.
"""
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import chromadb
from langchain_core.documents import Document

from src.rag.embeddings import embeddings
from src.config import CHROMA_PERSIST_DIR, RAG_TOP_K

_client: Optional["chromadb.ClientAPI"] = None


def _get_client() -> "chromadb.ClientAPI":
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)
    return _client


def _collection_name(thread_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", thread_id)
    return f"thread_{safe}"[:63]


def _collection_exists(thread_id: str) -> bool:
    """Check existence via list_collections() -- never via get_or_create,
    which would silently create an empty collection as a side effect."""
    name = _collection_name(thread_id)
    return any(c.name == name for c in _get_client().list_collections())


def has_sources(thread_id: str) -> bool:
    if not _collection_exists(thread_id):
        return False
    return _get_client().get_collection(_collection_name(thread_id)).count() > 0


def list_sources(thread_id: str) -> List[Dict[str, Any]]:
    """Distinct uploaded files for this thread, with chunk counts."""
    if not _collection_exists(thread_id):
        return []
    collection = _get_client().get_collection(_collection_name(thread_id))
    result = collection.get(include=["metadatas"])

    by_source: Dict[str, Dict[str, Any]] = {}
    for meta in result.get("metadatas") or []:
        source_id = meta.get("source_id")
        if source_id is None:
            continue
        entry = by_source.setdefault(
            source_id,
            {
                "source_id": source_id,
                "filename": meta.get("filename", "unknown"),
                "uploaded_at": meta.get("uploaded_at", ""),
                "num_chunks": 0,
            },
        )
        entry["num_chunks"] += 1
    return sorted(by_source.values(), key=lambda s: s["uploaded_at"])


def add_documents(thread_id: str, source_id: str, chunks: List[Document]) -> int:
    """Embed and store one uploaded file's chunks. Returns the chunk count stored."""
    uploaded_at = datetime.now(timezone.utc).isoformat()
    for chunk in chunks:
        chunk.metadata["uploaded_at"] = uploaded_at

    texts = [chunk.page_content for chunk in chunks]
    metadatas = [chunk.metadata for chunk in chunks]
    ids = [f"{source_id}_{i}" for i in range(len(chunks))]
    embedding_vectors = embeddings.embed_documents(texts)

    collection = _get_client().get_or_create_collection(_collection_name(thread_id))
    collection.add(ids=ids, embeddings=embedding_vectors, documents=texts, metadatas=metadatas)
    return len(chunks)


def delete_source(thread_id: str, source_id: str) -> bool:
    """Delete all chunks belonging to one uploaded file. Returns whether anything was deleted."""
    if not _collection_exists(thread_id):
        return False
    collection = _get_client().get_collection(_collection_name(thread_id))
    existing = collection.get(where={"source_id": source_id}, include=[])
    ids = existing.get("ids") or []
    if not ids:
        return False
    collection.delete(ids=ids)
    return True


def query(thread_id: str, query_text: str, k: int = RAG_TOP_K) -> List[Dict[str, Any]]:
    """Top-k relevant chunks for a query. Empty list if no sources are uploaded."""
    if not _collection_exists(thread_id):
        return []
    query_embedding = embeddings.embed_query(query_text)
    collection = _get_client().get_collection(_collection_name(thread_id))
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )
    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]
    return [
        {
            "content": doc,
            "filename": meta.get("filename", "unknown"),
            "page": meta.get("page"),
            "score": dist,
        }
        for doc, meta, dist in zip(docs, metas, dists)
    ]
