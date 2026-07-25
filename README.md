```
                                                                                          ███╗   ███╗██╗   ██╗██╗  ████████╗██╗     █████╗  ██████╗ ███████╗███╗   ██╗████████╗
                                                                                          ████╗ ████║██║   ██║██║  ╚══██╔══╝██║    ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
                                                                                          ██╔████╔██║██║   ██║██║     ██║   ██║    ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║
                                                                                          ██║╚██╔╝██║██║   ██║██║     ██║   ██║    ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║
                                                                                          ██║ ╚═╝ ██║╚██████╔╝███████╗██║   ██║    ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║
                                                                                          ╚═╝     ╚═╝ ╚═════╝ ╚══════╝╚═╝   ╚═╝    ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝
                                                                                                   ██████╗██╗  ██╗ █████╗ ████████╗██████╗  ██████╗ ████████╗
                                                                                                  ██╔════╝██║  ██║██╔══██╗╚══██╔══╝██╔══██╗██╔═══██╗╚══██╔══╝
                                                                                                  ██║     ███████║███████║   ██║   ██████╔╝██║   ██║   ██║
                                                                                                  ██║     ██╔══██║██╔══██║   ██║   ██╔══██╗██║   ██║   ██║
                                                                                                  ╚██████╗██║  ██║██║  ██║   ██║   ██████╔╝╚██████╔╝   ██║
                                                                                                   ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ╚═════╝  ╚═════╝    ╚═╝
                                                                                                            ~  powered by LangChain + LangGraph  ~
```

# Multi-Agent Chatbot

A general-purpose chatbot built on **LangChain + LangGraph**, fronted by
**FastAPI**, **Celery**, and **Streamlit**. A supervisor-routed agent graph
searches the web (Tavily), scrapes specific pages (trafilatura), synthesizes
findings, and answers with cited sources. Runs against a local **Ollama**
model or any OpenAI-compatible LLM.

---

## Running the app

There are two ways to run it, depending on what you need:

| Option | Use when | Gets you |
|---|---|---|
| [A — Docker](#option-a--docker-recommended) | You just want it running, on Linux/macOS/Windows | The full stack: UI + API + worker + Redis |
| [B — CLI only](#option-b--cli-only-no-celery-no-ui) | You're debugging the LangGraph agent itself | Just the graph, no web layer |

Both options need at least one LLM backend configured: either a local
**Ollama** install with a model pulled, or an `OPENAI_API_KEY`. See
[Switching LLMs](#switching-llms) below. Web search additionally needs a
[Tavily](https://tavily.com/) API key (`TAVILY_API_KEY`).

### Option A — Docker (recommended)

Prerequisites: Docker Desktop, plus Ollama running natively on the host
(pull at least one model, e.g. `ollama pull llama3.1:8b`) — unless you're
using the OpenAI backend, in which case only `OPENAI_API_KEY` is needed.

```bash
# 1. Configure secrets
cp .env.example .env    # or create .env manually
# Edit .env and set TAVILY_API_KEY (required for web search) and
# OPENAI_API_KEY (required unless you switch to the local Ollama LLM).

# 2. Build and launch everything (redis, api, worker, ui)
docker compose up --build

# 3. Open the UI
#    http://localhost:8501
```

That's it — Streamlit is now talking to FastAPI, which dispatches to the
Celery worker running the LangGraph agent. Ask a question in the chat box
and watch `docker compose logs -f worker` to see the agents route.

Useful commands:

```bash
docker compose logs -f worker                        # tail worker logs
docker compose up -d --scale worker=4                 # run 4 workers
docker compose exec redis redis-cli flushall           # clear conversation state
docker compose down                                    # stop, keep Redis data
docker compose down -v                                 # stop and wipe data
```

### Option B — CLI only (no Celery, no UI)

Useful for debugging the graph directly, without standing up Redis, FastAPI,
or Streamlit. Requires Python 3.12 and either a local Ollama install or an
`OPENAI_API_KEY`.

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

python chat_script.py                              # interactive mode
python chat_script.py "question 1" "question 2"    # batch mode
```

---

## Required environment variables

Set in `.env` (see [§4.4](#44-central-configuration-srcconfigpy) below for the full list):

```
TAVILY_API_KEY=tvly-...      # required for web search
OPENAI_API_KEY=sk-...        # required when using ChatOpenAI (the current default)
```

---

## Switching LLMs

Edit `src/agents/llm.py` and (un)comment the desired block:

- **Local Ollama**: `ChatOllama(model="llama3.1:8b")`. Pull the model first:
  `ollama pull llama3.1:8b`. For noticeably better routing and
  structured-output compliance on small models, try `qwen2.5:7b`.
- **OpenAI** (current default): `ChatOpenAI(model="gpt-4o-mini")`. Requires
  `OPENAI_API_KEY`.

The `OLLAMA_BASE_URL` env var is honored automatically, so the same code runs
on the host (`http://localhost:11434`) and in Docker
(`http://host.docker.internal:11434`).

Embeddings follow the same toggle pattern in `src/rag/embeddings.py`
(Ollama `nomic-embed-text` vs. OpenAI `text-embedding-3-small`) — keep it in
sync with `llm.py` when switching providers.

---

## Architecture

This section is the full architectural walkthrough: the multi-agent brain,
the service layer around it, and the Docker Compose orchestration that ties
everything together.

### 1. High-level topology

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

A user's question travels **ui → api → redis → worker → LangGraph → (LLM +
tools) → redis → api → ui**. The multi-agent graph lives inside the Celery
worker.

### 2. The LangGraph brain

The entire agent logic lives under `src/agents/`. The orchestration is a
`StateGraph` compiled with a memory checkpointer.

```
          +-------+
          | START |
          +---+---+
              |
              v
        +------------+
   +--->| Supervisor |---+
   |    +-----+------+   |
   |          |           |
   |    (routes to one)   |
   |    /   /  \   \  \   |
   |   v   v    v   v   v
   | +--+ +--+ +--+ +--+ +--+
   | |OR| |WS| |SC| |RA| |AR|
   | +-++ +-++ +-++ +-++ +-++
   |   |    |    |    |    |
   +---+----+----+----+----+
              |
              v
           +-----+
           | END |
           +-----+

OR = Orchestrator   WS = Web Searcher   SC = Web Scraper
RA = Research Analyst   AR = Answer Refiner
```

Every non-terminal node routes **back to the supervisor**. The supervisor is
the single routing authority; there are no direct node→node shortcuts. This
makes the flow inspectable and lets the supervisor handle arbitrary plan
shapes (search-only, scrape-only, search+scrape, neither).

#### 2.1 Agents (nodes in the graph)

| Agent | File | Role |
|---|---|---|
| **Orchestrator** | `nodes/orchestrator.py::orchestrator_node` | Reads the user's question, writes a plan naming which downstream agents to run. Never answers the user directly. |
| **Web Searcher** | `nodes/web_searcher.py::web_searcher_node` | LLM formulates a Tavily query → 5 search results (title + url + snippet). Records URLs into `cited_urls`. |
| **Web Scraper** | `nodes/web_scraper.py::web_scraper_node` | LLM picks 1–3 URLs (from search results, the plan, or constructed via known patterns like `github.com/<user>?tab=repositories&sort=stargazers`). `trafilatura.fetch_url` + `trafilatura.extract` pull the main text (boilerplate-stripped). Truncates to 6000 chars/URL. Records successful URLs into `cited_urls`. |
| **Research Analyst** | `nodes/research_analyst.py::research_analyst_node` | Synthesizes search snippets + scraped text into structured notes keeping each fact next to its source URL. |
| **Answer Refiner** | `nodes/answer_refiner.py::answer_refiner_node` | Produces the final user-facing answer with inline `[source](url)` citations taken from `cited_urls`, plus a `**Sources:**` section. Sets `resolved=True`. |
| **Supervisor (Speaker Selector)** | `nodes/speaker_selector.py::speaker_selector_node` | Router. Picks the next agent from the state. Uses `llm.with_structured_output(NextSpeaker)` so the LLM is forced to return one of the 6 valid literal names. Has a deterministic code-level fallback if the LLM mis-routes. |

#### 2.2 Shared state

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

#### 2.3 Supervisor decision procedure

Rules applied in order (first match wins); agents already in
`executed_agents` are **banned** from selection:

1. `answer_refiner` is in `executed_agents` → **END**
2. `orchestrator` is **not** in `executed_agents` → **orchestrator**
3. Plan mentions *Web Searcher* and `web_searcher` not executed → **web_searcher**
4. Plan mentions *Web Scraper* and `web_scraper` not executed → **web_scraper**
5. (`web_searcher` or `web_scraper` in executed) and `research_analyst` not executed → **research_analyst**
6. Otherwise → **answer_refiner**

The LLM is constrained by `Literal` types in a Pydantic schema (`src/schemas.py`), so invalid
strings are impossible. If the LLM picks an already-executed agent (possible
with weak models), a deterministic fallback in `speaker_selector_node` runs
the same rules in Python.

#### 2.4 Why this design handles small local models

Small Ollama models (e.g. `gemma3:4b`, `llama3.1:8b`) tend to ignore prompt
constraints and produce free-form text. Two mitigations are baked in:

- **Structured output** (`with_structured_output`) on the supervisor and the
  scraper — the LLM literally cannot return anything other than the allowed
  shape.
- **Explicit banned-agent logic in the prompt** (the "GOLDEN RULE") reinforced
  by a Python-side safety net that overrides a bad pick.

For noticeably better compliance on routing and URL construction, switch to
`qwen2.5:7b` or `gpt-4o` in `src/agents/llm.py`.

#### 2.5 Citations

`cited_urls` is the single source of truth for citations. Both the searcher
and the scraper append URLs to it; the answer refiner is prompted to cite
**only** URLs present in that list, which prevents hallucinated sources.

### 3. Conversation flows

**Simple question (no web search)** — e.g. "What is recursion?"
```
Supervisor -> Orchestrator (plan: skip search, go to Answer Refiner)
Supervisor -> Answer Refiner (provides explanation)
Supervisor -> END
```
`executed_agents = [orchestrator, answer_refiner]`

**Question requiring web search** — e.g. "What is the latest news about OpenAI?"
```
Supervisor -> Orchestrator (plan: search, analyze, refine)
Supervisor -> Web Searcher (searches Tavily)
Supervisor -> Research Analyst (analyzes results into structured notes)
Supervisor -> Answer Refiner (crafts final response with citations)
Supervisor -> END
```
`executed_agents = [orchestrator, web_searcher, research_analyst, answer_refiner]`

**Question requiring deep page scraping** — e.g. "What is the most starred repo of GitHub user X?"
```
Supervisor -> Orchestrator (plan: scrape a constructed URL, analyze, refine)
Supervisor -> Web Scraper (LLM picks the URL; trafilatura extracts the content)
Supervisor -> Research Analyst (ranks/extracts from the scraped page)
Supervisor -> Answer Refiner (final answer with source citation)
Supervisor -> END
```
`executed_agents = [orchestrator, web_scraper, research_analyst, answer_refiner]`

**Search + scrape** — e.g. "Summarize the main findings of the latest CERN Higgs boson paper."
```
Supervisor -> Orchestrator (plan: search, then scrape the paper URL, analyze, refine)
Supervisor -> Web Searcher (finds candidate URLs via Tavily)
Supervisor -> Web Scraper (extracts the full text with trafilatura)
Supervisor -> Research Analyst (synthesizes snippets + full text)
Supervisor -> Answer Refiner (cites the paper URL)
Supervisor -> END
```
`executed_agents = [orchestrator, web_searcher, web_scraper, research_analyst, answer_refiner]`

**Greeting** — e.g. "Hello!"
```
Supervisor -> Orchestrator (plan: delegate to Answer Refiner)
Supervisor -> Answer Refiner (responds with greeting)
Supervisor -> END
```
`executed_agents = [orchestrator, answer_refiner]`

### 4. Service layer

#### 4.1 FastAPI (`src/api.py`)

Thin HTTP veneer on top of Celery.

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness check. Used by Streamlit's sidebar and Docker's healthcheck. |
| `POST /question/` | Body: `{ "prompt": str, "thread_id": str? }`. Dispatches `process_chat_task` to Celery. Returns `{ "task_id": str }`. |
| `GET /answer/{task_id}` | Poll endpoint. Returns one of `Pending` / `Completed` / `Failed`. Handles all Celery states correctly. |

Everything is typed via Pydantic `ChatRequest` / `ChatResponse` /
`AnswerResponse` (`src/schemas.py`), with route handlers split out into
`src/routers/chat.py` and `src/routers/sources.py`.

#### 4.2 Celery worker (`src/tasks.py`)

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

#### 4.3 Streamlit (`app.py`)

- Renders the banner, chat history, sample questions, sidebar (session UUID,
  API health, new-chat button).
- Generates a `thread_id` per browser session (`uuid.uuid4()`).
- Calls `POST /question/`, then polls `GET /answer/{task_id}` every
  `RESPONSE_POLL_INTERVAL` seconds up to `RESPONSE_TIMEOUT_SECONDS`.
- Streams the answer word-by-word via `st.write_stream`.

#### 4.4 Central configuration (`src/config.py`)

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
| `OPENAI_API_KEY` | — | `ChatOpenAI` (currently the active LLM) |
| `TAVILY_API_KEY` | — | Tavily web search |

This is why the same code runs unchanged on the host, on WSL, or in Docker —
you just rewire the URLs via environment variables.

### 5. Docker orchestration

#### 5.1 Services

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

#### 5.2 Networking

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

#### 5.3 Why Ollama stays on the host

Running Ollama inside a container on Windows requires the NVIDIA Container
Toolkit + WSL GPU passthrough configuration, which is brittle and you'd lose
the integration with Ollama's native update/model-management tooling. The
speedup from GPU-native Ollama is so large that it almost always dominates
any container-orchestration upside.

#### 5.4 Health checks & startup order

- `redis`: `redis-cli ping` every 5s. Must be healthy before anything else starts.
- `api`: `curl /health` every 10s. `ui` waits for `api` to become healthy before launching.
- `worker`: depends on `redis` being healthy.

This eliminates the "Celery starts before Redis is ready" race you'd
otherwise hit.

#### 5.5 Data & state

- `redis-data` named volume persists keys across `docker compose down`
  restarts. `docker compose down -v` wipes it (useful when clearing stuck
  task state).
- LangGraph's `MemorySaver` checkpointer currently stores conversation
  memory **in the worker process's RAM**. Two implications:
  - A single worker is fine for one user.
  - Scaling to multiple workers requires swapping in a Redis-backed
    checkpointer (`langgraph.checkpoint.redis.RedisSaver`) so any worker can
    pick up any thread. Simple refactor when you need it.

#### 5.6 Dev vs. prod compose

- `docker-compose.yml`: production-ish. Image is self-contained; code is
  baked in at build time.
- `docker-compose.override.yml`: automatically merged on `docker compose up`.
  Bind-mounts `./` into `/app` and enables `uvicorn --reload`. You get hot
  reload on the API and the UI. For the worker, run `docker compose restart
  worker` after editing agent/graph code.
- To run the prod-like stack only: `docker compose -f docker-compose.yml up`.

#### 5.7 Common commands

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

### 6. Request lifecycle (end-to-end)

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

All LLM calls in step 6 go to the configured LLM backend — natively on the
host via `http://host.docker.internal:11434` for Ollama, or to the OpenAI API
when `ChatOpenAI` is active.

### 7. Extension points

| Goal | How |
|---|---|
| Add another tool (e.g. SQL, a vector store) | Add a node file under `src/agents/nodes/`, export it from `nodes/__init__.py`, register it in `graph.py`, add a new `Literal` to `NextSpeaker` (`src/schemas.py`), update the `orchestrator` and `speaker_selector` prompts with the new agent's description and routing rules. |
| Swap LLM per-agent (e.g. GPT-4o for the supervisor, Llama for the rest) | `src/agents/agents.py` instantiates each chain independently; you can bind a different `llm` to each. |
| Persist conversations across worker restarts | Replace `MemorySaver` in `src/agents/graph.py` with `RedisSaver` from `langgraph-checkpoint-redis`. |
| Observability | Add `flower` to compose (`docker compose up -d flower`) for a Celery dashboard, or wire OpenTelemetry into FastAPI + LangChain. |
| Deploy to a cloud | The compose file runs on any Docker host. Move Ollama into a GPU-enabled container or switch the LLM to a cloud provider via `src/agents/llm.py`. |

### 8. File map

```
.
├── Dockerfile                       # shared image for api/worker/ui
├── docker-compose.yml               # prod-ish stack
├── docker-compose.override.yml      # dev: bind-mount + --reload
├── .dockerignore
├── app.py                           # Streamlit UI entry
├── chat_script.py                   # CLI entry (bypasses Celery/FastAPI, uses graph directly)
├── requirements.txt
├── prompts/
│   └── agent_prompts.yaml           # all agent system prompts
├── src/
│   ├── api.py                       # FastAPI app: creates `app`, includes routers, /health
│   ├── schemas.py                   # every Pydantic model (agent structured-output + API DTOs)
│   ├── tasks.py                     # Celery app + chat/RAG tasks
│   ├── config.py                    # env-driven configuration
│   ├── banner.py                    # shared ASCII banner
│   ├── routers/
│   │   ├── chat.py                  # POST /question/, GET /answer/{task_id}
│   │   └── sources.py               # /sources/* RAG upload/list/delete routes
│   ├── rag/                         # personal source upload/retrieval (Chroma-backed)
│   │   ├── embeddings.py            # OllamaEmbeddings / OpenAIEmbeddings selector
│   │   ├── ingest.py                # parsing + chunking for uploaded PDF/TXT/MD
│   │   └── vectorstore.py           # per-thread Chroma collections
│   └── agents/
│       ├── llm.py                   # ChatOllama / ChatOpenAI selector
│       ├── state.py                 # GraphState TypedDict
│       ├── agents.py                # LangChain runnables per agent
│       ├── nodes/                   # one graph node per file (including tool calls)
│       ├── graph.py                 # StateGraph wiring
│       ├── ci_agent.py              # thin wrapper around the compiled graph
│       └── utils.py                 # format_history, SSL patch, pipeline helpers
└── ui/
    ├── style.css
    └── display_utils/
        ├── utils.py                 # sample questions
        └── sources.py               # sidebar: upload/list/delete personal sources
```
