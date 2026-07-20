import dotenv
import yaml
from typing import List, Literal
from pydantic import BaseModel, Field

from src.agents.llm import llm
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
dotenv.load_dotenv()


AgentName = Literal[
    "web_searcher",
    "web_scraper",
    "research_analyst",
    "answer_refiner",
]


class NextSpeaker(BaseModel):
    """The next agent to run in the multi-agent workflow."""
    speaker: Literal[
        "orchestrator",
        "web_searcher",
        "web_scraper",
        "research_analyst",
        "answer_refiner",
        "END",
    ] = Field(description="Name of the next agent to run.")


class Pipeline(BaseModel):
    """Orchestrator's plan, expressed as an ordered list of agents to run."""
    reasoning: str = Field(
        description="Brief (1-3 sentences) explanation of why this pipeline was chosen."
    )
    pipeline: List[AgentName] = Field(
        description=(
            "Ordered list of agents to run, AFTER the orchestrator. "
            "MUST end with 'answer_refiner'. "
            "Include 'web_searcher' and/or 'web_scraper' ONLY when real-world "
            "information is needed. Include 'research_analyst' whenever "
            "'web_searcher' or 'web_scraper' is in the list."
        )
    )


class ScrapeTargets(BaseModel):
    """URLs selected for full-content scraping."""
    urls: List[str] = Field(
        description="Fully-qualified http(s) URLs to fetch and scrape. 1-3 URLs."
    )


with open('./prompts/agent_prompts.yaml', 'r') as file:
    prompts = yaml.safe_load(file)

#-------------------------------Orchestrator------------------------------------------------------]
orchestrator_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompts["orchestrator"]["prompt"]),
        ("human", "Context: {context}"),
    ]
)
orchestrator_agent = orchestrator_prompt | llm.with_structured_output(Pipeline)
#-------------------------------Web Searcher------------------------------------------------------]
web_searcher_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompts["web_searcher"]["prompt"]),
        ("human", "Question: {question}\nOrchestrator's Plan: {plan}"),
    ]
)
web_searcher_agent = web_searcher_prompt | llm | StrOutputParser()
#-------------------------------Web Scraper-------------------------------------------------------]
web_scraper_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompts["web_scraper"]["prompt"]),
        (
            "human",
            "Question: {question}\nOrchestrator's Plan: {plan}\n"
            "Conversation history: {history}\n"
            "Existing search results (may be empty):\n{search_results}",
        ),
    ]
)
web_scraper_agent = web_scraper_prompt | llm.with_structured_output(ScrapeTargets)
#-------------------------------Research Analyst--------------------------------------------------]
research_analyst_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompts["research_analyst"]["prompt"]),
        (
            "human",
            "Question: {question}\n"
            "Search Results:\n{search_results}\n\n"
            "Scraped Page Content:\n{scraped_content}",
        ),
    ]
)
research_analyst_agent = research_analyst_prompt | llm | StrOutputParser()
#-------------------------------AnswerRefiner------------------------------------------------]
answer_refiner_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompts["answer_refiner"]["prompt"]),
        ("human", "Context: {context}"),
    ]
)
answer_refiner_agent = answer_refiner_prompt | llm | StrOutputParser()
#-------------------------------Speaker Selector------------------------------------------------
speaker_selector_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompts["speaker_selector"]["prompt"]),
        ("human", "Context: {context}"),
    ]
)
speaker_selector_agent = speaker_selector_prompt | llm.with_structured_output(NextSpeaker)
