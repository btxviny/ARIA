from loguru import logger

from src.agents.graph import app as graph


class CIAgent:
    """Thin wrapper around the compiled LangGraph app.

    The LangGraph checkpointer keys conversation memory by `thread_id`, so the
    caller is responsible for passing a unique id per conversation (e.g. per
    Streamlit session).
    """

    def __init__(self):
        self.graph = graph

    def generate_reply(self, query: str, thread_id: str = "default") -> dict:
        config = {"configurable": {"thread_id": thread_id}}
        inputs = {
            "question": query,
            "executed_agents": [],
            "pipeline": [],
            "plan": "",
            "code_run_id": "",
            "code_files": [],
            "code_result": "",
            "data_files": [],
        }
        try:
            event = None
            for event in self.graph.stream(inputs, config, stream_mode="values"):
                pass
            if event is None:
                return {"error": "Graph produced no output"}

            logger.info(f"[thread_id={thread_id}] Final state keys: {list(event.keys())}")
            messages = event.get("messages", [])
            final_answer = messages[-1].content if messages else ""
            logger.success(f"[thread_id={thread_id}] Final response: {final_answer[:200]}...")
            return {
                "answer": final_answer,
                "code_files": event.get("code_files", []),
                "code_run_id": event.get("code_run_id", ""),
                "code_result": event.get("code_result", ""),
            }
        except Exception as e:
            logger.exception(f"[thread_id={thread_id}] Error during agent execution")
            return {"error": str(e)}
