from typing import Any, Dict

from langchain_core.messages import RemoveMessage
from loguru import logger

from src.agents.agents import history_summarizer_agent
from src.agents.state import GraphState
from src.agents.utils import format_history
from src.config import HISTORY_SUMMARY_TRIGGER, HISTORY_WINDOW_SIZE


def history_manager_node(state: GraphState) -> Dict[str, Any]:
    """Windows conversation history.

    Runs first on every turn. Once the checkpointed message list exceeds
    HISTORY_SUMMARY_TRIGGER, the oldest messages (everything beyond the most
    recent HISTORY_WINDOW_SIZE) are folded into a rolling summary and removed
    from state via RemoveMessage, so prompts and the checkpointer stay
    bounded regardless of how long the conversation runs.
    """
    messages = state.get("messages", [])
    if len(messages) <= HISTORY_SUMMARY_TRIGGER:
        return {}

    to_summarize = messages[:-HISTORY_WINDOW_SIZE]
    if not to_summarize:
        return {}

    try:
        new_summary = history_summarizer_agent.invoke({
            "summary": state.get("summary", ""),
            "new_lines": format_history(to_summarize),
        })
    except Exception as e:
        logger.warning(f"History manager: summarization failed, keeping full history this turn: {e}")
        return {}

    logger.info(f"History manager: folded {len(to_summarize)} messages into rolling summary.")
    return {
        "summary": new_summary,
        "messages": [RemoveMessage(id=m.id) for m in to_summarize if m.id is not None],
    }
