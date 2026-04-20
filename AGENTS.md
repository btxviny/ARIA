# Multi-Agent Chatbot Architecture

This document describes the multi-agent architecture powering this chatbot, built with **LangChain** and **LangGraph**.

## Architecture Overview

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

OR = Orchestrator
WS = Web Searcher (Tavily snippets)
SC = Web Scraper (trafilatura full-page extraction)
RA = Research Analyst
AR = Answer Refiner
```

All agents route back to the **Supervisor** after execution. The Supervisor decides who goes next based on the orchestrator's plan and which agents have already run.

## Agents

### 1. Supervisor (Speaker Selector)

**Role**: Traffic controller for the entire conversation flow.

**How it works**:
- Receives the current state (question, plan, executed agents, history).
- Calls the LLM to decide which agent should execute next.
- Validates the LLM output against the set of known agents (`orchestrator`, `web_searcher`, `web_scraper`, `research_analyst`, `answer_refiner`, `END`) using a Pydantic `Literal` schema (`with_structured_output`).
- If the LLM returns an invalid agent name, falls back to a sensible default based on what has already executed.
- Uses LangGraph's `Command(goto=...)` to route to the selected agent.

**When it terminates**: When the answer has been refined (the `resolved` flag is set), it routes to `END`.

---

### 2. Orchestrator

**Role**: Analyzes the user's question and creates an execution plan.

**How it works**:
- Receives the conversation history and the user's question.
- Determines whether the question requires web search (factual/current info) or can be answered directly (greetings, explanations, opinions).
- Produces a numbered plan specifying which agents to use and in what order.
- Never answers the user directly.

**Output**: A plan string stored in `state.plan`.

**Example plan** (web search needed):
```
1. Use the Web Searcher Agent to search for latest SpaceX news.
2. Pass results to the Research Analyst Agent to analyze.
3. Delegate to the Answer Refiner Agent for the final response.
```

**Example plan** (no web search):
```
1. Delegate to the Answer Refiner Agent to explain recursion.
```

---

### 3. Web Searcher

**Role**: Formulates a search query and fetches real-time results from the web.

**How it works**:
- Takes the user's question and the orchestrator's plan.
- Uses the LLM to generate an optimized search query string.
- Calls the **Tavily Search API** with that query to retrieve up to 5 web results.
- Each result includes: title, URL, and content snippet.
- Stores the raw results in `state.search_results`.

**When it's used**: Only when the orchestrator's plan calls for web search (current events, factual lookups, news, etc.).

**Dependencies**: Requires `TAVILY_API_KEY` in the `.env` file.

---

### 4. Web Scraper

**Role**: Fetches and extracts the full text content of specific URLs.

**How it works**:
- Receives the user's question, the orchestrator's plan, conversation history, and (optionally) prior Tavily search results.
- Uses the LLM (with `with_structured_output(ScrapeTargets)`) to pick 1–3 target URLs. These can be URLs returned by the Web Searcher OR custom URLs constructed by the LLM using well-known patterns (e.g. `https://github.com/<user>?tab=repositories&sort=stargazers`).
- Fetches each URL with `trafilatura.fetch_url` and extracts the main content with `trafilatura.extract` (plain-text, no boilerplate).
- Truncates each page to `SCRAPE_MAX_CHARS_PER_URL` (6000 chars) to stay within context limits.
- Stores the concatenated content in `state.scraped_content` and appends each successfully scraped URL to `state.cited_urls`.

**When it's used**: When the orchestrator's plan names "Web Scraper" — typically for questions that need detailed content living on a specific page (rankings, full article text, repo lists, tables, etc.) that Tavily snippets can't provide.

**Dependencies**: `trafilatura`.

---

### 5. Research Analyst

**Role**: Analyzes and synthesizes raw material (search snippets AND scraped page content) into structured insights.

**How it works**:
- Receives the user's question, `search_results` (from Web Searcher), and `scraped_content` (from Web Scraper). Either may be empty; at least one is non-empty when this agent runs.
- Extracts key facts, dates, numbers, names, rankings, and other details — preserving the source URL next to each fact so the Answer Refiner can cite it.
- Cross-references information across sources.
- Produces a structured analysis (bullet points, sections).
- Stores the analysis as an `AIMessage` in the conversation history.

**When it's used**: Runs after the Web Searcher and/or Web Scraper. Never runs without at least one of them.

---

### 6. Answer Refiner

**Role**: Produces the final user-facing response.

**How it works**:
- Receives the full context: conversation history, question, plan, research analysis, search results, scraped content, and the `cited_urls` list.
- Crafts a clear, concise response.
- **Inline citations**: every claim derived from web sources is cited as `[source](<url>)`, using URLs from `cited_urls`.
- Appends a `**Sources:**` section listing each cited URL at the bottom of web-sourced answers.
- Sets the `resolved` flag to `True`, signaling the Supervisor to end the conversation.

**When it's used**: Always the last agent before `END`. Every conversation flow ends with the Answer Refiner.

---

## Conversation Flows

### Flow 1: Simple Question (no web search)

```
User: "What is recursion?"

Supervisor -> Orchestrator (creates plan: skip search, go to Answer Refiner)
Supervisor -> Answer Refiner (provides explanation)
Supervisor -> END
```

Executed agents: `[orchestrator, answer_refiner]`

### Flow 2: Question Requiring Web Search

```
User: "What is the latest news about OpenAI?"

Supervisor -> Orchestrator (creates plan: search, analyze, refine)
Supervisor -> Web Searcher (searches Tavily for "OpenAI latest news 2026")
Supervisor -> Research Analyst (analyzes 5 search results into structured notes)
Supervisor -> Answer Refiner (crafts final response with citations)
Supervisor -> END
```

Executed agents: `[orchestrator, web_searcher, research_analyst, answer_refiner]`

### Flow 3: Question Requiring Deep Page Scraping

```
User: "What is the most starred repo of GitHub user btxviny?"

Supervisor -> Orchestrator (plan: scrape github.com/btxviny?tab=repositories&sort=stargazers, analyze, refine)
Supervisor -> Web Scraper (LLM picks that URL; trafilatura extracts the repo list)
Supervisor -> Research Analyst (ranks repos by stars from the scraped page)
Supervisor -> Answer Refiner (final answer with source citation)
Supervisor -> END
```

Executed agents: `[orchestrator, web_scraper, research_analyst, answer_refiner]`

### Flow 4: Search + Scrape

```
User: "Summarize the main findings of the latest CERN Higgs boson paper."

Supervisor -> Orchestrator (plan: search, then scrape the paper URL, analyze, refine)
Supervisor -> Web Searcher (finds candidate paper URLs via Tavily)
Supervisor -> Web Scraper (extracts the full paper text with trafilatura)
Supervisor -> Research Analyst (synthesizes snippets + full text)
Supervisor -> Answer Refiner (cites the paper URL)
Supervisor -> END
```

Executed agents: `[orchestrator, web_searcher, web_scraper, research_analyst, answer_refiner]`

### Flow 5: Greeting

```
User: "Hello!"

Supervisor -> Orchestrator (creates plan: delegate to Answer Refiner)
Supervisor -> Answer Refiner (responds with greeting)
Supervisor -> END
```

Executed agents: `[orchestrator, answer_refiner]`

---

## State

The shared state (`GraphState`) flows through all agents:

| Field | Type | Description |
|-------|------|-------------|
| `messages` | `list` | Conversation history (HumanMessage / AIMessage) |
| `next` | `str` | Next agent to execute |
| `executed_agents` | `List[str]` | Tracks which agents have already run |
| `resolved` | `bool` | Whether the answer has been finalized |
| `question` | `str` | The original user question |
| `plan` | `str` | The orchestrator's execution plan |
| `search_results` | `str` | Raw web search results from Tavily |
| `scraped_content` | `str` | Full-page text extracted by trafilatura, keyed by URL |
| `cited_urls` | `List[str]` | Deduplicated URLs collected from Web Searcher and Web Scraper, used by the Answer Refiner for inline citations |

---

## Configuration

### LLM

Configured in `src/agents/llm.py`. Three options available (uncomment the one you want):

- **OpenAI GPT-4o** (cloud, fast, paid)
- **Ollama Gemma 3 4B** (local, free, fast, no reasoning)
- **Ollama Qwen 3.5** (local, free, slower, reasoning model)

### API Keys

Set in `.env`:

```
OPENAI_API_KEY=sk-...        # Required for OpenAI LLM
TAVILY_API_KEY=tvly-...      # Required for web search
```
