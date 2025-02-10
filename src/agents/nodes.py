from typing import Any, Dict

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END
from langgraph.types import Command
from loguru import logger

from src.agents.agents import (
    orchestrator_agent,
    sql_agent,
    visualization_agent,
    speaker_selector_agent,
    answer_refiner_agent
)
from src.agents.state import GraphState
from src.agents.utils import load_resources, format_history, process_and_run_script, execute_sql_query

# Load resources (job posts and news metadata)
job_posts_df_metadata, news_df_metadata = load_resources()

def speaker_selector_node(state: GraphState) -> str:
    """
    Selects the speaker for the next message.
    """
    # If answer_refiner has already responded, terminate the conversation
    if state.get("resolved", False):
        logger.debug("Answer already refined, terminating conversation.")
        return Command(goto=END, update={"next": END, "resolved": False})
    
    # Create the context for the speaker selector agent
    context = f"""
        History: {format_history(state.get("messages", []))}, 
        Question: {state.get("question", "")}, 
        Orchestrator's plan: {state.get("plan", "")}, 
        executed_agents: {state.get("executed_agents", [])}
    """
    # Select the speaker based on the context
    speaker = speaker_selector_agent.invoke({"context": context})
    logger.debug(f"Speaker Selector selected next speaker: {speaker}")
    if speaker == "END":
        speaker = END
    
    return Command(goto=speaker, update={"next": speaker})


def orchestrator_node(state: GraphState) -> str:
    """
    Routes a question to either document retrieval or a direct response to the user.
    """
    context = f"""
        History: {format_history(state.get("messages", []))}, 
        Question: {state.get("question", "")}
    """
    messages = state.get("messages", [])
    if len(messages) > 10:
        logger.debug("Clipping Message History to last 10 messages.")
        messages = messages[-10:]

    # Invoke the orchestrator agent to generate a plan
    plan = orchestrator_agent.invoke({"context": context})
    logger.warning(f"Orchestrator generated Plan: {plan}")
    return {
        "messages": [HumanMessage(content=state.get("question", ""))], 
        "plan": plan, 
        "executed_agents": state.get("executed_agents", []) + ['orchestrator']
    }


def sql_node(state: GraphState) -> Dict[str, Any]:
    """
    Executes an SQL query to retrieve data based on the question.
    """
    
    # Generate the SQL query using the sql agent
    query = sql_agent.invoke({
        "job_posts_df_metadata": job_posts_df_metadata, 
        "news_df_metadata": news_df_metadata, 
        "context": state.get("question","")
    })
    logger.info(f"Generated SQL query: {query}")
    
    # Execute the SQL query and capture the results
    results = execute_sql_query(query)
    logger.info(f"SQL query executed. Results: {results}")
    return {
        "executed_agents": state.get("executed_agents", []) + ['sql'],
        "query_result": results
    }


def visualization_node(state: GraphState) -> Dict[str, Any]:
    """
    Generates and runs a visualization script based on the query result.
    """
    context = f"""
        History: {format_history(state.get("messages", []))}, 
        Question: {state.get("question", "")}, 
        Multi-Agent framework solution plan: {state.get("plan", "")}, 
        Query Result: {state.get("query_result", "")}
    """
    # Generate the visualization script using the visualization agent
    response = visualization_agent.invoke({"context": context})
    script = response.script
    filename = response.file_name
    logger.warning(f"Visualization script generated: {script}")
    logger.warning(f"Visualization script saved to: {filename}")
    process_and_run_script(script)
    logger.info("Visualization script executed.")
    return {
        "visualization_script": script,
        "generated_file": filename,
        "executed_agents": state.get("executed_agents", []) + ['visualization']
    }


def answer_refiner_node(state: GraphState) -> Dict[str, Any]:
    """
    Refines the answer by using the answer refiner agent.
    """
    context = f"""
        History: {[msg.content for msg in state.get("messages", [])]},
        Question: {state.get("question", "")},
        Multi-Agent framework solution plan: {state.get("plan", "")},
        Query Result: {state.get("query_result", "")}
    """
    # Refine the answer using the answer refiner agent
    answer = answer_refiner_agent.invoke({"context": context})
    logger.info(f"Refined answer: {answer}")
    return {
            "messages": AIMessage(content=answer), 
            "plan": "",
            "executed_agents": state.get("executed_agents", []) + ['answer_refiner'],
            "resolved": True,
        }
