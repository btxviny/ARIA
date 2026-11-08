# ARIA Modernization TODO

Ordered by priority. Check items off as they land.

## 1. Security & correctness (do first)

- [ ] Re-enable TLS verification
  - [ ] Remove `httpx.Client(verify=False)` in `src/agents/llm.py`
  - [ ] Remove/gate the urllib3 monkeypatch in `src/agents/utils.py` (`init_ssl_context`)
  - [ ] Add opt-in `SSL_VERIFY=false` or CA bundle via `SSL_CERT_FILE` for proxy setups
- [ ] Harden the code executor (`src/agents/nodes/code_executor.py`)
  - [ ] Run the subprocess with a scrubbed env (no API keys, no DB/Redis URLs)
  - [ ] Add CPU/memory limits
  - [ ] Longer term: run in a throwaway container with no network, or a hosted sandbox (E2B/Modal)
- [ ] Replace `MemorySaver` in `src/agents/graph.py` with `PostgresSaver` (`langgraph-checkpoint-postgres`) so memory survives restarts and multiple workers
- [ ] Stop swallowing errors in `src/tasks.py` (`except Exception: pass` around `init_schema()`)
- [ ] Move DB schema setup to Alembic migrations
- [ ] Move Postgres password out of `docker-compose.yml` into `.env`
- [ ] Stop publishing Postgres/Redis ports to the host (or bind to `127.0.0.1`)

## 2. Quality tooling & CI

- [ ] Add `pyproject.toml` with `ruff` and `mypy`/`pyright` config
- [ ] Add `pre-commit` config
- [ ] Add `pytest` and a `tests/` directory
  - [ ] Unit tests: `_clean_code`, `dedup_urls`, `format_history`, schemas
  - [ ] Graph routing tests with a fake LLM (no API calls)
  - [ ] LLM eval set seeded from `test_prompts.yaml`
- [ ] GitHub Actions workflow: lint, type-check, tests, Docker build on every PR
- [ ] Enable Dependabot or Renovate

## 3. Packaging & Docker

- [x] Migrate `requirements.txt` to `pyproject.toml` + `uv` with a committed `uv.lock`
- [x] Pin dependency versions
- [ ] Split dependencies into groups (api, ui, worker, sandbox libs)
- [ ] Multi-stage Dockerfile with separate slim `ui`/`api` and `worker` targets
- [ ] Run containers as a non-root user; drop `build-essential` from final stage
- [ ] Replace `./:/app` bind mounts in `docker-compose.override.yml` with `develop: watch`
- [ ] Add a healthcheck for the worker (`celery inspect ping`)
- [ ] Add `/ready` endpoint alongside `/health`
- [ ] Add `Makefile`/`justfile` (`up`, `test`, `lint`, `logs`)
- [ ] Add `LICENSE`
- [ ] Publish images to GHCR from CI, tagged by commit SHA

## 4. Architecture

- [ ] Replace `src/config.py` with `pydantic-settings` (typed, validated, fail-fast)
- [ ] LLM layer
  - [ ] Use `init_chat_model` with `LLM_PROVIDER` / `LLM_MODEL` env vars (remove comment-toggled blocks)
  - [ ] Add timeouts, retries, and a fallback model
- [ ] Stream progress and tokens to the UI (`astream_events` + SSE/WebSocket, Redis pub/sub) instead of 0.5s polling
- [ ] Decide on Celery: keep, or move to async FastAPI + LangGraph + Postgres checkpointer (or Arq/Temporal)
- [ ] Evaluate replacing orchestrator + speaker selector with a tool-calling agent / `langgraph-supervisor`
- [ ] RAG
  - [ ] Move Chroma to a server, or switch to `pgvector`
  - [ ] Upgrade embeddings beyond `all-MiniLM-L6-v2`
  - [ ] Add hybrid search (BM25 + vectors) and a reranker
- [ ] Scraping: consider Tavily `extract` or Playwright for JS-heavy pages
- [ ] UI
  - [ ] Split `app.py` (465 lines) into pages/components
  - [ ] Evaluate Chainlit / assistant-ui / custom frontend for native streaming chat

## 5. Observability & deployment

- [ ] Tracing: LangSmith or Langfuse
- [ ] Structured JSON logging
- [ ] `/metrics` endpoint for Prometheus
- [ ] API authentication and rate limiting before any non-localhost exposure
- [ ] Simple deploy path: single VM + compose + Caddy for TLS
- [ ] Update `README.md` to match all of the above

## Suggested order

1. TLS + code-executor env scrubbing
2. ruff + pytest + GitHub Actions CI
3. uv + pinned deps + split Docker images
4. Postgres checkpointer + pgvector
5. Streaming progress + tracing, then revisit Celery
