"""FastAPI application entrypoint: wires up routers and the health check.

Route handlers live in `src/routers/`. This process must never touch
`src/rag/vectorstore.py` directly -- see `src/routers/sources.py` and
`src/rag/vectorstore.py` for why.
"""
import sys

from fastapi import FastAPI

from src.banner import BANNER
from src.routers import chat, sources

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

app = FastAPI(title="Multi-Agent Chatbot API", version="1.0.0")

print(BANNER)

app.include_router(chat.router)
app.include_router(sources.router)


@app.get("/health")
def health() -> dict:
    """Simple liveness check."""
    return {"status": "ok"}
