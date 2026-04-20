from dotenv import load_dotenv
from langgraph.graph import START, END, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from src.agents.state import GraphState
from src.agents.nodes import (
    orchestrator_node,
    speaker_selector_node,
    web_searcher_node,
    research_analyst_node,
    answer_refiner_node,
)
from loguru import logger

load_dotenv()
memory = MemorySaver()

workflow = StateGraph(GraphState)

workflow.add_edge(START, "supervisor")
workflow.add_node("supervisor", speaker_selector_node)
workflow.add_node("orchestrator", orchestrator_node)
workflow.add_node("web_searcher", web_searcher_node)
workflow.add_node("research_analyst", research_analyst_node)
workflow.add_node("answer_refiner", answer_refiner_node)

workflow.add_edge("orchestrator", "supervisor")
workflow.add_edge("web_searcher", "supervisor")
workflow.add_edge("research_analyst", "supervisor")
workflow.add_edge("answer_refiner", "supervisor")

app = workflow.compile(checkpointer=memory)

app.get_graph().draw_mermaid_png(output_file_path="graph.png")
