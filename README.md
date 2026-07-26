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

A general-purpose AI chatbot powered by a team of specialized agents that collaborate to answer questions. It can search the web, read pages, run code, and chat over your own documents — all with cited sources.

![UI screenshot](ui.png)

---

## Capabilities

- **Web search** — searches the web via Tavily and answers current-events questions the model's training data can't handle
- **Deep page reading** — fetches and reads full pages (documentation, GitHub profiles, papers, articles) to extract specific information
- **Cited answers** — every response includes inline source links; citations only come from pages the agents actually visited
- **Document Q&A** — upload PDF, TXT, or Markdown files; the app chunks and indexes them so you can ask questions about your own content
- **Code generation & execution** — writes and runs Python in a sandboxed environment, returning output and any generated files (charts, CSVs, etc.) directly in chat
- **Multi-turn memory** — the full conversation history is replayed on every turn, so follow-up questions work naturally

---

## Tech stack

| Layer | Technology |
|---|---|
| **UI** | Streamlit |
| **API** | FastAPI |
| **Task queue** | Celery + Redis |
| **Agent orchestration** | LangGraph (StateGraph) |
| **LLM integration** | LangChain (`ChatOpenAI` / `ChatOllama`) |
| **Web search** | Tavily API |
| **Web scraping** | trafilatura |
| **Document storage** | Chroma (vector store, per session) |
| **Embeddings** | OpenAI or Ollama embeddings |

---

## Architecture

Questions flow through four services before reaching the user:

```
Browser → Streamlit UI → FastAPI → Redis → Celery Worker → LangGraph agents → LLM
```

- The **UI** (Streamlit) handles chat display, file uploads, and session management.
- The **API** (FastAPI) receives questions and dispatches them as background tasks.
- The **worker** (Celery) picks up tasks from Redis and runs the agent graph.
- The **agent graph** (LangGraph) is where the actual reasoning happens.

### Agent graph

A **supervisor** routes each turn through a team of specialist agents. Every agent reports back to the supervisor, which decides what to do next:

```
START → Orchestrator → Supervisor → [Web Searcher] → [Web Scraper] → Research Analyst → Answer Refiner → END
```

| Agent | Role |
|---|---|
| **Orchestrator** | Reads the question and writes a plan — which tools are needed, in what order |
| **Web Searcher** | Queries Tavily and returns the top results with titles, URLs, and snippets |
| **Web Scraper** | Fetches and extracts the full text from 1–3 URLs using trafilatura |
| **Research Analyst** | Synthesizes search results and scraped content into structured notes |
| **Answer Refiner** | Writes the final response with inline citations from visited URLs |
| **Supervisor** | Routes between agents; ensures each agent runs at most once per turn |

Simple questions (e.g. "What is recursion?") skip straight to the Answer Refiner. Complex ones trigger the full pipeline. The supervisor adapts the path based on what the question actually needs.

---

## Running the app

### Docker (recommended)

```bash
cp .env.example .env
# Add TAVILY_API_KEY and your LLM settings to .env
docker compose up --build
```

Open **http://localhost:8501**.

### Command line

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python chat_script.py
```

---

## Environment variables

```
TAVILY_API_KEY=tvly-...    # required for web search
OPENAI_API_KEY=sk-...      # required when using OpenAI (the default)
```

The app also supports local models via Ollama or any OpenAI-compatible server — configure in `src/agents/llm.py`.
