from typing import List, Annotated
from langgraph.graph import MessagesState
from langgraph.graph.message import add_messages

class GraphState(MessagesState):
    next: str
    messages: Annotated[list, add_messages]
    summary: str
    executed_agents: List[str]
    resolved: bool
    question: str
    plan: str
    pipeline: List[str]
    search_results: str
    search_status: str
    search_error: str
    scraped_content: str
    cited_urls: List[str]
    rag_context: str
    cited_sources: List[str]
    code_result: str
    code_error: str
    code_files: List[dict]
    code_run_id: str
    data_files: List[dict]
