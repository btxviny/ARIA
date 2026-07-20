"""Celery tasks that wrap the multi-agent graph.

A single `CIAgent` instance is shared across tasks (the LangGraph app is
stateless; per-conversation memory lives in the graph checkpointer keyed by
`thread_id`).
"""
from celery import Celery
from loguru import logger

from src.agents.ci_agent import CIAgent
from src.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND

app = Celery(
    "multiagent_chatbot",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

ci_agent = CIAgent()


@app.task
def process_chat_task(prompt: str, thread_id: str = "default") -> dict:
    """Run the agent graph for a single user turn.

    Parameters
    ----------
    prompt : str
        The user's question.
    thread_id : str
        Identifier for the conversation memory. Each UI session should pass
        its own id so separate chats do not share history.
    """
    try:
        reply = ci_agent.generate_reply(query=prompt, thread_id=thread_id)
        return {"answer": reply.get("answer", ""), "thread_id": thread_id}
    except Exception as e:
        logger.exception(f"process_chat_task failed for thread_id={thread_id}")
        return {"error": str(e), "thread_id": thread_id}
