import os
from typing import Any, Dict

import ssl
import urllib3
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END
from langgraph.types import Command
from loguru import logger
from tavily import TavilyClient

from src.agents.agents import (
    orchestrator_agent,
    speaker_selector_agent,
    web_searcher_agent,
    research_analyst_agent,
    answer_refiner_agent
)
from src.agents.state import GraphState
from src.agents.utils import format_history

VALID_SPEAKERS = {"orchestrator", "web_searcher", "research_analyst", "answer_refiner", "END"}

# Disable SSL verification for requests
os.environ['REQUESTS_CA_BUNDLE'] = ''
os.environ['CURL_CA_BUNDLE'] = ''

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Monkey-patch urllib3 to disable SSL verification globally
import urllib3.util.ssl_
def create_urllib3_context_no_verify(*args, **kwargs):
    context = urllib3.util.ssl_.create_urllib3_context_original(*args, **kwargs)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context

urllib3.util.ssl_.create_urllib3_context_original = urllib3.util.ssl_.create_urllib3_context
urllib3.util.ssl_.create_urllib3_context = create_urllib3_context_no_verify

tavily_client = TavilyClient(api_key=os.environ.get("TAVILY_API_KEY"))


def _parse_speaker(raw: str) -> str:
    """Extract a valid speaker name from the LLM output."""
    cleaned = raw.strip().lower()
    for valid in VALID_SPEAKERS:
        if valid.lower() in cleaned:
            return valid
    return None


def speaker_selector_node(state: GraphState) -> str:
    if state.get("resolved", False):
        logger.debug("Answer already refined, terminating conversation.")
        return Command(goto=END, update={"next": END, "resolved": False})
    
    context = f"""
        History: {format_history(state.get("messages", []))}, 
        Question: {state.get("question", "")}, 
        Orchestrator's plan: {state.get("plan", "")}, 
        executed_agents: {state.get("executed_agents", [])}
    """
    raw_speaker = speaker_selector_agent.invoke({"context": context})
    speaker = _parse_speaker(raw_speaker)

    if speaker is None:
        executed = state.get("executed_agents", [])
        if "orchestrator" not in executed:
            speaker = "orchestrator"
        elif "web_searcher" in executed and "research_analyst" not in executed:
            speaker = "research_analyst"
        else:
            speaker = "answer_refiner"
        logger.warning(f"Speaker Selector returned invalid speaker '{raw_speaker.strip()}', falling back to: {speaker}")

    logger.debug(f"Speaker Selector selected next speaker: {speaker}")
    if speaker == "END":
        speaker = END
    
    return Command(goto=speaker, update={"next": speaker})


def orchestrator_node(state: GraphState) -> str:
    context = f"""
        History: {format_history(state.get("messages", []))}, 
        Question: {state.get("question", "")}
    """
    messages = state.get("messages", [])
    if len(messages) > 10:
        logger.debug("Clipping Message History to last 10 messages.")
        messages = messages[-10:]

    plan = orchestrator_agent.invoke({"context": context})
    logger.warning(f"Orchestrator generated Plan: {plan}")
    return {
        "messages": [HumanMessage(content=state.get("question", ""))], 
        "plan": plan, 
        "executed_agents": state.get("executed_agents", []) + ['orchestrator']
    }


def web_searcher_node(state: GraphState) -> Dict[str, Any]:
    """Generates a search query and executes it via Tavily."""
    question = state.get("question", "")
    plan = state.get("plan", "")

    search_query = web_searcher_agent.invoke({"question": question, "plan": plan})
    logger.info(f"Web Searcher generated query: {search_query}")

    try:
        response = tavily_client.search(query=search_query, max_results=5)
        results = []
        for r in response.get("results", []):
            results.append(f"Title: {r['title']}\nURL: {r['url']}\nContent: {r['content']}\n")
        search_results = "\n---\n".join(results)
    except Exception as e:
        logger.error(f"Tavily search failed: {e}")
        search_results = f"Search failed: {str(e)}"

    logger.info(f"Web Searcher found {len(response.get('results', []))} results")
    return {
        "search_results": search_results,
        "executed_agents": state.get("executed_agents", []) + ['web_searcher']
    }


def research_analyst_node(state: GraphState) -> Dict[str, Any]:
    """Analyzes raw search results and produces structured insights."""
    question = state.get("question", "")
    search_results = state.get("search_results", "")

    analysis = research_analyst_agent.invoke({
        "question": question,
        "search_results": search_results
    })
    logger.info(f"Research Analyst produced analysis: {analysis[:200]}...")

    return {
        "messages": [AIMessage(content=f"[Research Analysis]\n{analysis}")],
        "executed_agents": state.get("executed_agents", []) + ['research_analyst']
    }


def answer_refiner_node(state: GraphState) -> Dict[str, Any]:
    context = f"""
        History: {[msg.content for msg in state.get("messages", [])]},
        Question: {state.get("question", "")},
        Multi-Agent framework solution plan: {state.get("plan", "")},
        Search Results: {state.get("search_results", "")}
    """
    answer = answer_refiner_agent.invoke({"context": context})
    logger.info(f"Refined answer: {answer}")
    return {
            "messages": AIMessage(content=answer), 
            "plan": "",
            "executed_agents": state.get("executed_agents", []) + ['answer_refiner'],
            "resolved": True,
        }
