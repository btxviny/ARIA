"""Command-line interface for the Multi-Agent Chatbot.

Usage:
  python chat_script.py                      # interactive mode
  python chat_script.py "question 1" "q2"    # batch mode (each arg = one turn)
"""
import sys
import uuid

from dotenv import load_dotenv
from loguru import logger

from src.agents.graph import app
from src.banner import BANNER

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

load_dotenv()

# One thread_id for the whole CLI session so turns share conversation memory.
THREAD_ID = str(uuid.uuid4())
config = {"configurable": {"thread_id": THREAD_ID}}

print(BANNER)


def process_query(query: str) -> None:
    """Process a single query through the agent graph."""
    inputs = {"question": query, "executed_agents": []}
    event = None
    for event in app.stream(inputs, config, stream_mode="values"):
        pass
    if event is None:
        logger.error("Graph produced no output")
        return
    logger.info(f"Final state keys: {list(event.keys())}")
    final_answer = event.get("messages", [{}])[-1].content
    logger.success(f"Final response: {final_answer}")


def main() -> None:
    logger.info(f"System is ready. thread_id={THREAD_ID}")

    if len(sys.argv) > 1:
        queries = sys.argv[1:]
        logger.info(f"Running {len(queries)} query(ies) from command-line arguments.")
        for i, query in enumerate(queries, start=1):
            logger.info(f"--- Query {i}/{len(queries)}: {query} ---")
            process_query(query)
    else:
        while True:
            query = input("Your question: ")
            if query.lower() == "exit":
                logger.info("User terminated the session.")
                break
            if query.strip():
                process_query(query)


if __name__ == "__main__":
    main()
