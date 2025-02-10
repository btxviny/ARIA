import copy
import json
from loguru import logger

from src.agents.graph import app as graph

class CIAgent:
    def __init__(self):
        self.graph = graph
        self.config = {"configurable": {"thread_id": "1"}}
    
    def generate_reply(self, query):
        try:
            inputs = {"question": query, "executed_agents": [], "generated_file" : ""}
            for event in graph.stream(inputs, self.config, stream_mode="values"):
                pass
            logger.info(f"Final state: {event}")
            final_answer = event.get("messages",[{}])[-1].content
            generated_file = event.get("generated_file", "")
            logger.success(f"Final response: {final_answer}")
            return {
                "answer": final_answer, 
                "generated_file": generated_file, 
            }
        except Exception as e:
            self.code_executor.code_executor.stop()                          
            return {"error": str(e)}
