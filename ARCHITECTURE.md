# Multi-Agent Chatbot — Architecture

This document explains the full system end-to-end: the multi-agent brain built
on **LangChain + LangGraph**, the **Celery / FastAPI / Streamlit** service
layer around it, and the **Docker Compose** orchestration that ties everything
together.

---

## 1. High-level topology

```
                     ┌──────────────────────────────────────────┐
                     │              host machine                │
                     │                                          │
                     │   Ollama (native, GPU-accelerated)       │
                     │     :11434                               │
                     │         ▲                                │
                     │         │ http (langchain_ollama)        │
                     │         │                                │
                     │  ┌──────┴───── docker compose ────────┐  │
   browser ──────────┼─►│  ui (Streamlit)  :8501             │  │
                     │  │       │                            │  │
                     │  │       │ POST /question             │  │
                     │  │       │ GET  /answer/{id}          │  │
                     │  │       ▼                            │  │
                     │  │  api (FastAPI)   :5000             │  │
                     │  │       │                            │  │
                     │  │       │ apply_async                │  │
                     │  │       ▼                            │  │
                     │  │  redis (broker + result backend)   │  │
                     │  │       ▲                            │  │
                     │  │       │ consume tasks              │  │
                     │  │       │                            │  │
                     │  │  worker (Celery → LangGraph)       │  │
                     │  │       │                            │  │
                     │  │       ├── Tavily API (web search)  │  │
                     │  │       ├── trafilatura (scraping)   │──┼──► internet
                     │  │       └── Ollama (LLM inference) ──┼──┘
                     │  └────────────────────────────────────┘  │
                     └──────────────────────────────────────────┘
```

A user's question travels **ui → api → redis → worker → LangGraph → (LLM + tools) → redis → api → ui**. The multi-agent graph lives inside the Celery worker.

---

## 2. The LangGraph brain

The entire agent logic lives under `src/agents/`. The orchestration is a
`StateGraph` compiled with a memory checkpointer.

### 2.1 Agents (nodes in the graph)

| Agent | File | Role |
|---|---|---|
| **Orchestrator** | `src/agents/nodes.py::orchestrator_node` | Reads the user's question, writes a plan naming which downstream agents to run. Never answers the user directly. |
| **Web Searcher** | `nodes.py::web_searcher_node` | LLM formulates a Tavily query → 5 search results (title + url + snippet). Records URLs into `cited_urls`. |
| **Web Scraper** | `nodes.py::web_scraper_node` | LLM picks 1–3 URLs (from search results, the plan, or constructed via known patterns like `github.com/<user>?tab=repositories&sort=stargazers`). `trafilatura.fetch_url` + `trafilatura.extract` pull the main text (boilerplate-stripped). Truncates to 6000 chars/URL. Records successful URLs into `cited_urls`. |
| **Research Analyst** | `nodes.py::research_analyst_node` | Synthesizes search snippets + scraped text into structured notes keeping each fact next to its source URL. |
| **Answer Refiner** | `nodes.py::answer_refiner_node` | Produces the final user-facing answer with inline `[source](url)` citations taken from `cited_urls`. Sets `resolved=True`. |
| **Supervisor (Speaker Selector)** | `nodes.py::speaker_selector_node` | Router. Picks the next agent from the state. Uses `llm.with_structured_output(NextSpeaker)` so the LLM is forced to return one of the 6 valid literal names. Has a deterministic code-level fallback if the LLM mis-routes. |

### 2.2 Shared state

The graph passes a single `GraphState` TypedDict through every node
(`src/agents/state.py`):

| Field | Type | Purpose |
|---|---|---|
| `messages` | `list` | Append-only conversation log (`HumanMessage`, `AIMessage`). |
| `next` | `str` | Next agent chosen by the supervisor. |
| `executed_agents` | `list[str]` | Ordered list of agents that have already run. Used by the supervisor's "no re-run" rules. |
| `resolved` | `bool` | `True` once `answer_refiner` finishes → triggers `END`. |
| `question` | `str` | The current turn's user question. |
| `plan` | `str` | Orchestrator's text plan. |
| `search_results` | `str` | Raw Tavily output (title/url/content). |
| `scraped_content` | `str` | trafilatura extractions, keyed by URL. |
| `cited_urls` | `list[str]` | Deduplicated URLs used across searcher + scraper; consumed by the refiner for citations. |

### 2.3 Graph topology

```
            START
              │
              ▼
        ┌───────────┐
        │orchestrator│
        └─────┬─────┘
              ▼
        ┌───────────┐
    ┌──►│ supervisor│──► END
    │   └─────┬─────┘
    │         │ (dispatches)
    │   ┌─────┴─────┬─────────────┬─────────────┐
    │   ▼           ▼             ▼             ▼
    │ web_searcher  web_scraper   research_…    answer_refiner
    │   │           │             │             │
    └───┴───────────┴─────────────┴─────────────┘
                (every node returns here)
```

Every non-terminal node routes **back to the supervisor**. The supervisor is
the single routing authority; there are no direct node→node shortcuts. This
makes the flow inspectable and lets the supervisor handle arbitrary plan
shapes (search-only, scrape-only, search+scrape, neither).

### 2.4 Supervisor decision procedure

Rules applied in order (first match wins); agents already in
`executed_agents` are **banned** from selection:

1. `answer_refiner` is in `executed_agents` → **END**
2. `orchestrator` is **not** in `executed_agents` → **orchestrator**
3. Plan mentions *Web Searcher* and `web_searcher` not executed → **web_searcher**
4. Plan mentions *Web Scraper* and `web_scraper` not executed → **web_scraper**
5. (`web_searcher` or `web_scraper` in executed) and `research_analyst` not executed → **research_analyst**
6. Otherwise → **answer_refiner**

The LLM is constrained by `Literal` types in a Pydantic schema, so invalid
strings are impossible. If the LLM picks an already-executed agent (possible
with weak models), a deterministic fallback in `speaker_selector_node` runs
the same rules in Python.

### 2.5 Why this design handles small local models

Small Ollama models (e.g. `gemma3:4b`, `llama3.1:8b`) tend to ignore prompt
constraints and produce free-form text. Two mitigations are baked in:

- **Structured output** (`with_structured_output`) on the supervisor and the
  scraper — the LLM literally cannot return anything other than the allowed
  shape.
- **Explicit banned-agent logic in the prompt** (the "GOLDEN RULE") reinforced
  by a Python-side safety net that overrides a bad pick.

For noticeably better compliance on routing and URL construction, switch to
`qwen2.5:7b` or `gpt-4o` in `src/agents/llm.py`.

### 2.6 Citations

`cited_urls` is the single source of truth for citations. Both the searcher
and the scraper append URLs to it; the answer refiner is prompted to cite
**only** URLs present in that list, which prevents hallucinated sources.

---

## 3. Service layer

### 3.1 FastAPI (`src/api.py`)

Thin HTTP veneer on top of Celery.

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness check. Used by Streamlit's sidebar and Docker's healthcheck. |
| `POST /question/` | Body: `{ "prompt": str, "thread_id": str? }`. Dispatches `process_chat_task` to Celery. Returns `{ "task_id": str }`. |
| `GET /answer/{task_id}` | Poll endpoint. Returns one of `Pending` / `Completed` / `Failed`. Handles all Celery states correctly (unlike the previous implementation, which could `.get()` on a FAILURE and 500). |

Everything is typed via Pydantic `ChatRequest` / `ChatResponse` /
`AnswerResponse`.

### 3.2 Celery worker (`src/tasks.py`)

Single task `process_chat_task(prompt, thread_id)` that wraps
`CIAgent.generate_reply`. `thread_id` is the LangGraph checkpointer key, so
each Streamlit session gets its own conversation memory — sessions do **not**
interfere with each other.

Why Celery and not just running the graph inline in FastAPI?

- **Long tasks off the request path**: an agent turn can take 5–60 seconds
  with a local LLM. Blocking an HTTP worker is unacceptable.
- **Concurrency**: scale workers independently (`docker compose up --scale
  worker=4`) without changing the API.
- **Retry + observability**: Celery gives us retries, state tracking, and a
  result backend for free.

### 3.3 Streamlit (`app.py`)

- Renders the banner, chat history, sample questions, sidebar (session UUID,
  API health, new-chat button).
- Generates a `thread_id` per browser session (`uuid.uuid4()`).
- Calls `POST /question/`, then polls `GET /answer/{task_id}` every
  `RESPONSE_POLL_INTERVAL` seconds up to `RESPONSE_TIMEOUT_SECONDS`.
- Streams the answer word-by-word via `st.write_stream`.

### 3.4 Central configuration (`src/config.py`)

Every tunable reads from an environment variable with a sensible default:

| Variable | Default | Used by |
|---|---|---|
| `REDIS_URL` | `redis://localhost:6379` | Celery broker/backend |
| `CELERY_BROKER_URL` | `REDIS_URL` | Celery |
| `CELERY_RESULT_BACKEND` | `REDIS_URL` | Celery |
| `API_HOST` | `0.0.0.0` | FastAPI |
| `API_PORT` | `5000` | FastAPI |
| `API_BASE_URL` | `http://localhost:5000` | Streamlit client |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | `ChatOllama` |
| `RESPONSE_TIMEOUT_SECONDS` | `180` | Streamlit polling |
| `RESPONSE_POLL_INTERVAL` | `0.5` | Streamlit polling |
| `OPENAI_API_KEY` | — | `ChatOpenAI` (optional) |
| `TAVILY_API_KEY` | — | Tavily web search |

This is why the same code runs unchanged on the host, on WSL, or in Docker —
you just rewire the URLs via environment variables.

---

## 4. Docker orchestration

### 4.1 Services

Defined in `docker-compose.yml`:

| Service | Image | Port | Role |
|---|---|---|---|
| `redis` | `redis:7-alpine` | 6379 | Broker + result backend |
| `api` | built from `Dockerfile` | 5000 | FastAPI |
| `worker` | same image as `api` | — | Celery worker running the LangGraph |
| `ui` | same image as `api` | 8501 | Streamlit |

`api`, `worker`, and `ui` share one image (`multiagent-chatbot:latest`) built
once from the repo's `Dockerfile`. This keeps the Docker cache hot and avoids
inconsistent dep versions between services.

### 4.2 Networking

Docker Compose creates a default bridge network where services reach each
other by service name:

| From → To | URL |
|---|---|
| api/worker → redis | `redis://redis:6379` |
| ui → api | `http://api:5000` |
| api/worker → Ollama (on host) | `http://host.docker.internal:11434` |
| browser → ui | `http://localhost:8501` |
| browser → api (for curl/debug) | `http://localhost:5000` |

`host.docker.internal` exists automatically on Windows/macOS Docker Desktop.
On Linux we add `extra_hosts: ["host.docker.internal:host-gateway"]` so the
same URL works everywhere.

### 4.3 Why Ollama stays on the host

Running Ollama inside a container on Windows requires the NVIDIA Container
Toolkit + WSL GPU passthrough configuration, which is brittle and you'd lose
the integration with Ollama's native update/model-management tooling. The
speedup from GPU-native Ollama is so large that it almost always dominates
any container-orchestration upside.

### 4.4 Health checks & startup order

- `redis`: `redis-cli ping` every 5s. Must be healthy before anything else starts.
- `api`: `curl /health` every 10s. `ui` waits for `api` to become healthy before launching.
- `worker`: depends on `redis` being healthy.

This eliminates the "Celery starts before Redis is ready" race you previously hit.

### 4.5 Data & state

- `redis-data` named volume persists keys across `docker compose down`
  restarts. `docker compose down -v` wipes it (useful when clearing stuck
  task state).
- LangGraph's `MemorySaver` checkpointer currently stores conversation
  memory **in the worker process's RAM**. Two implications:
  - A single worker is fine for one user.
  - Scaling to multiple workers requires swapping in a Redis-backed
    checkpointer (`langgraph.checkpoint.redis.RedisSaver`) so any worker can
    pick up any thread. Simple refactor when you need it.

### 4.6 Dev vs. prod compose

- `docker-compose.yml`: production-ish. Image is self-contained; code is
  baked in at build time.
- `docker-compose.override.yml`: automatically merged on `docker compose up`.
  Bind-mounts `./` into `/app` and enables `uvicorn --reload`. You get hot
  reload on the API and the UI. For the worker, run `docker compose restart
  worker` after editing agent/graph code.
- To run the prod-like stack only: `docker compose -f docker-compose.yml up`.

### 4.7 Common commands

```bash
# Build + bring up the stack (first run or after dep changes)
docker compose up --build

# Detached, tail logs
docker compose up -d
docker compose logs -f worker

# Scale workers for parallelism
docker compose up -d --scale worker=4

# Reset conversations (wipe Redis)
docker compose exec redis redis-cli flushall

# Shut down, keep Redis data
docker compose down

# Shut down AND wipe Redis volume
docker compose down -v

# Exec into a container for debugging
docker compose exec api bash
```

---

## 5. Request lifecycle (end-to-end)

A single user turn, traced through every component:

1. **Browser** — user types a question in Streamlit, hits enter.
2. **Streamlit (`ui`)** — appends to `display_history`, posts
   `{"prompt": "...", "thread_id": "<session-uuid>"}` to
   `http://api:5000/question/`.
3. **FastAPI (`api`)** — validates the prompt, calls
   `process_chat_task.apply_async(...)`. Celery serializes the payload and
   pushes it onto the Redis `celery` queue. Returns `{"task_id": "..."}`.
4. **Streamlit** — starts polling `GET /answer/{task_id}` every 0.5s.
5. **Celery worker** — picks up the task, calls
   `CIAgent.generate_reply(query, thread_id)`.
6. **LangGraph**:
   a. `START → orchestrator` — writes a plan.
   b. `supervisor` — reads plan + executed_agents, dispatches.
   c. `web_searcher` (if plan says so) — LLM → Tavily query → 5 results.
   d. `web_scraper` (if plan says so) — LLM picks URLs → trafilatura fetches
      and extracts the main text of each.
   e. `research_analyst` — synthesizes the collected raw material.
   f. `answer_refiner` — produces final answer with `[source](url)` citations
      from `cited_urls`; sets `resolved=True`.
   g. `supervisor` sees `resolved=True` → `END`.
7. **Celery worker** returns `{"answer": "...", "thread_id": "..."}`, which
   Celery stores in the Redis result backend under the task id.
8. **FastAPI `/answer/{task_id}`** — next poll sees `SUCCESS`, returns
   `{"status": "Completed", "result": {...}}`.
9. **Streamlit** — streams the answer word-by-word into the chat, appends to
   `display_history`.

All LLM calls in step 6 go to the native Ollama server on the host via
`http://host.docker.internal:11434`.

---

## 6. Extension points

| Goal | How |
|---|---|
| Add another tool (e.g. SQL, a vector store) | Add a node in `nodes.py`, register it in `graph.py`, add a new `Literal` to `NextSpeaker`, update the `orchestrator` and `speaker_selector` prompts with the new agent's description and routing rules. |
| Swap LLM per-agent (e.g. GPT-4o for the supervisor, Llama for the rest) | `src/agents/agents.py` instantiates each chain independently; you can bind a different `llm` to each. |
| Persist conversations across worker restarts | Replace `MemorySaver` in `src/agents/graph.py` with `RedisSaver` from `langgraph-checkpoint-redis`. |
| Observability | Add `flower` to compose (`docker compose up -d flower`) for a Celery dashboard, or wire OpenTelemetry into FastAPI + LangChain. |
| Deploy to a cloud | The compose file runs on any Docker host. Move Ollama into a GPU-enabled container or switch the LLM to a cloud provider via `src/agents/llm.py`. |

---

## 7. File map

```
.
├── Dockerfile                       # shared image for api/worker/ui
├── docker-compose.yml               # prod-ish stack
├── docker-compose.override.yml      # dev: bind-mount + --reload
├── .dockerignore
├── run.bat                          # native Windows launcher (non-docker)
├── app.py                           # Streamlit UI entry
├── chat_script.py                   # CLI entry (bypasses Celery/FastAPI, uses graph directly)
├── requirements.txt
├── prompts/
│   └── agent_prompts.yaml           # all agent system prompts
├── src/
│   ├── api.py                       # FastAPI app
│   ├── tasks.py                     # Celery app + process_chat_task
│   ├── config.py                    # env-driven configuration
│   ├── banner.py                    # shared ASCII banner
│   └── agents/
│       ├── llm.py                   # ChatOllama / ChatOpenAI selector
│       ├── state.py                 # GraphState TypedDict
│       ├── agents.py                # LangChain runnables per agent
│       ├── nodes.py                 # graph nodes (including tool calls)
│       ├── graph.py                 # StateGraph wiring
│       ├── ci_agent.py              # thin wrapper around the compiled graph
│       └── utils.py                 # format_history helper
└── ui/
    ├── style.css
    └── display_utils/utils.py       # sample questions
```
