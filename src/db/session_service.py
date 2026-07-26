"""PostgreSQL-backed session and message persistence.

Uses psycopg2-binary with a ThreadedConnectionPool. Safe to import in both
the FastAPI process (sync route handlers) and the Celery worker (--pool=solo,
single-process).

WARNING: ThreadedConnectionPool is NOT fork-safe. If Celery's pool is ever
changed from --pool=solo to --pool=prefork, the pool must be created lazily
inside each task (after the fork), not at module import time.

When POSTGRES_URL is not set, every public function logs a warning and returns
a safe default so the rest of the application continues working without a DB.
"""
from __future__ import annotations

import psycopg2.pool as pg_pool
from psycopg2.extras import Json
from loguru import logger

from src.config import POSTGRES_URL

_pool: pg_pool.ThreadedConnectionPool | None = None

_CREATE_SESSIONS = """
CREATE TABLE IF NOT EXISTS sessions (
    thread_id     TEXT PRIMARY KEY,
    title         TEXT NOT NULL DEFAULT '',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    message_count INT NOT NULL DEFAULT 0
);
"""

_CREATE_MESSAGES = """
CREATE TABLE IF NOT EXISTS messages (
    id            SERIAL PRIMARY KEY,
    thread_id     TEXT NOT NULL REFERENCES sessions(thread_id) ON DELETE CASCADE,
    role          TEXT NOT NULL,
    content       TEXT NOT NULL DEFAULT '',
    code_run_id   TEXT,
    code_files    JSONB,
    code_result   TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    message_index INT NOT NULL
);
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS messages_thread_idx
    ON messages (thread_id, message_index);
"""


def _get_pool() -> pg_pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        if not POSTGRES_URL:
            raise RuntimeError("POSTGRES_URL is not configured")
        _pool = pg_pool.ThreadedConnectionPool(minconn=1, maxconn=10, dsn=POSTGRES_URL)
    return _pool


def init_schema() -> None:
    """Create tables if they do not already exist. Idempotent."""
    if not POSTGRES_URL:
        logger.warning("POSTGRES_URL not set — session persistence is disabled")
        return
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(_CREATE_SESSIONS)
            cur.execute(_CREATE_MESSAGES)
            cur.execute(_CREATE_INDEX)
        conn.commit()
    finally:
        pool.putconn(conn)


def count_messages(thread_id: str) -> int:
    """Return the number of stored messages for a thread."""
    if not POSTGRES_URL:
        return 0
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM messages WHERE thread_id = %s",
                (thread_id,),
            )
            return cur.fetchone()[0]
    finally:
        pool.putconn(conn)


def upsert_session(thread_id: str, title: str, message_count: int) -> None:
    """Create or update a session row.

    The CASE expression ensures the title is only set on the first insert.
    Subsequent calls preserve the original title even when an empty string
    is passed (which happens on every turn after the first).
    """
    if not POSTGRES_URL:
        return
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO sessions (thread_id, title, message_count)
                VALUES (%s, %s, %s)
                ON CONFLICT (thread_id) DO UPDATE
                    SET updated_at    = NOW(),
                        message_count = EXCLUDED.message_count,
                        title         = CASE
                            WHEN sessions.title = '' THEN EXCLUDED.title
                            ELSE sessions.title
                        END
                """,
                (thread_id, title, message_count),
            )
        conn.commit()
    finally:
        pool.putconn(conn)


def save_message(
    thread_id: str,
    role: str,
    content: str,
    code_run_id: str | None,
    code_files: list | None,
    code_result: str | None,
    message_index: int,
) -> None:
    """Insert one message row."""
    if not POSTGRES_URL:
        return
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO messages
                    (thread_id, role, content, code_run_id,
                     code_files, code_result, message_index)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    thread_id,
                    role,
                    content,
                    code_run_id or None,
                    Json(code_files) if code_files else None,
                    code_result or None,
                    message_index,
                ),
            )
        conn.commit()
    finally:
        pool.putconn(conn)


def list_sessions(limit: int = 50) -> list[dict]:
    """Return sessions ordered by most-recently-updated, newest first."""
    if not POSTGRES_URL:
        return []
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT thread_id, title, created_at, updated_at, message_count
                FROM sessions
                ORDER BY updated_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall()
        return [
            {
                "thread_id": r[0],
                "title": r[1],
                "created_at": r[2].isoformat(),
                "updated_at": r[3].isoformat(),
                "message_count": r[4],
            }
            for r in rows
        ]
    finally:
        pool.putconn(conn)


def get_messages(thread_id: str) -> list[dict]:
    """Return all messages for a thread ordered by message_index."""
    if not POSTGRES_URL:
        return []
    pool = _get_pool()
    conn = pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT role, content, code_run_id,
                       code_files, code_result, message_index
                FROM messages
                WHERE thread_id = %s
                ORDER BY message_index
                """,
                (thread_id,),
            )
            rows = cur.fetchall()
        return [
            {
                "role": r[0],
                "content": r[1],
                "code_run_id": r[2] or "",
                "code_files": r[3] or [],
                "code_result": r[4] or "",
                "message_index": r[5],
            }
            for r in rows
        ]
    finally:
        pool.putconn(conn)
