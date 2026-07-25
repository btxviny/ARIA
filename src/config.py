"""Centralized application configuration.

All tunables live here so every component (API, Celery worker, Streamlit UI)
reads from the same place. Values can be overridden via environment variables
(typically set in the project `.env` file).
"""
import os
from dotenv import load_dotenv

load_dotenv()


# --- Celery / Redis ---------------------------------------------------------
REDIS_URL: str = os.environ.get("REDIS_URL", "redis://localhost:6379")
CELERY_BROKER_URL: str = os.environ.get("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND: str = os.environ.get("CELERY_RESULT_BACKEND", REDIS_URL)


# --- FastAPI ----------------------------------------------------------------
API_HOST: str = os.environ.get("API_HOST", "0.0.0.0")
API_PORT: int = int(os.environ.get("API_PORT", "5000"))
# The base URL the Streamlit UI uses to talk to the API. localhost is used
# (rather than 0.0.0.0) because the UI connects from the client side.
API_BASE_URL: str = os.environ.get("API_BASE_URL", f"http://localhost:{API_PORT}")


# --- LLM --------------------------------------------------------------------
# Base URL for a native Ollama server. Override to http://host.docker.internal:11434
# when running the stack in Docker on Windows/macOS.
OLLAMA_BASE_URL: str = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


# --- UI / polling -----------------------------------------------------------
# Max seconds the UI will wait for a single response.
RESPONSE_TIMEOUT_SECONDS: int = int(os.environ.get("RESPONSE_TIMEOUT_SECONDS", "180"))
# Seconds between answer-poll requests from the UI.
RESPONSE_POLL_INTERVAL: float = float(os.environ.get("RESPONSE_POLL_INTERVAL", "0.5"))
# Max seconds the UI will wait for a source to finish ingesting.
SOURCE_INGEST_TIMEOUT_SECONDS: int = int(os.environ.get("SOURCE_INGEST_TIMEOUT_SECONDS", "120"))


# --- RAG: personal source upload --------------------------------------------
# Directory (inside the worker container/host) where the Chroma persistent
# client stores its per-thread collections. Kept outside /app so the dev
# compose override's `./:/app` bind mount never shadows it.
CHROMA_PERSIST_DIR: str = os.environ.get("CHROMA_PERSIST_DIR", "./data/chroma")
# Chunks retrieved per RAG query.
RAG_TOP_K: int = int(os.environ.get("RAG_TOP_K", "5"))
# Hard cap on total chars of retrieved chunk text fed into the research analyst.
RAG_MAX_CONTEXT_CHARS: int = int(os.environ.get("RAG_MAX_CONTEXT_CHARS", "8000"))
# Chunking parameters used at ingest time.
RAG_CHUNK_SIZE: int = int(os.environ.get("RAG_CHUNK_SIZE", "1000"))
RAG_CHUNK_OVERLAP: int = int(os.environ.get("RAG_CHUNK_OVERLAP", "150"))
# Max upload size (megabytes), checked against decoded byte length.
MAX_UPLOAD_MB: int = int(os.environ.get("MAX_UPLOAD_MB", "15"))
