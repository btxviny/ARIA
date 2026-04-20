from typing import List, Annotated
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages

class GraphState(MessagesState):  
    next: str
    messages: Annotated[list, add_messages]
    executed_agents: List[str]
    resolved: bool
    question: str
    plan: str
    search_results: str
