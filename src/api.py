"""FastAPI application entrypoint: wires up routers and the health check.

Route handlers live in `src/routers/`. This process must never touch
`src/rag/vectorstore.py` directly -- see `src/routers/sources.py` and
`src/rag/vectorstore.py` for why.
"""
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.banner import BANNER
from src.db import session_service
from src.routers import chat, datafiles, files, sessions, sources

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        session_service.init_schema()
    except Exception:
        pass  # POSTGRES_URL not set or DB unreachable; logged inside init_schema
    yield


app = FastAPI(title="Multi-Agent Chatbot API", version="1.0.0", lifespan=lifespan)

print(BANNER)

app.include_router(chat.router)
app.include_router(sources.router)
app.include_router(files.router)
app.include_router(datafiles.router)
app.include_router(sessions.router)


@app.get("/health")
def health() -> dict:
    """Simple liveness check."""
    return {"status": "ok"}
