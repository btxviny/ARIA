from typing import List, Annotated
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages

class GraphState(MessagesState):  
    #speaker selector 
    next: str
    messages: Annotated[list, add_messages]
    executed_agents: List[str]
    resolved: bool
    #orchestrator
    question: str
    plan: str
    #sql
    query_result: str
    #visualization
    visualization_script: str
    generated_file: str
   