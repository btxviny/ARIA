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
    pipeline: List[str]
    search_results: str
    scraped_content: str
    cited_urls: List[str]
