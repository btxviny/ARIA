import dotenv
import yaml

from src.agents.llm import llm
from src.schemas import CodeGenOutput, NextSpeaker, Pipeline, ScrapeTargets
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
dotenv.load_dotenv()


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
#-------------------------------History Summarizer------------------------------------------------]
history_summarizer_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompts["history_summarizer"]["prompt"]),
        (
            "human",
            "Previous summary (may be empty):\n{summary}\n\n"
            "New conversation turns to incorporate:\n{new_lines}",
        ),
    ]
)
history_summarizer_agent = history_summarizer_prompt | llm | StrOutputParser()
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
#-------------------------------RAG Retriever-----------------------------------------------------]
rag_retriever_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompts["rag_retriever"]["prompt"]),
        (
            "human",
            "Question: {question}\nOrchestrator's Plan: {plan}\n"
            "Conversation history: {history}",
        ),
    ]
)
rag_retriever_agent = rag_retriever_prompt | llm | StrOutputParser()
#-------------------------------Research Analyst--------------------------------------------------]
research_analyst_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompts["research_analyst"]["prompt"]),
        (
            "human",
            "Question: {question}\n"
            "Search Results:\n{search_results}\n\n"
            "Scraped Page Content:\n{scraped_content}\n\n"
            "Document Context (from the user's uploaded sources):\n{rag_context}",
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
#-------------------------------Code Executor---------------------------------------------------]
code_executor_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompts["code_executor"]["prompt"]),
        (
            "human",
            "Question: {question}\nOrchestrator's Plan: {plan}\n"
            "Search Results (if any):\n{search_results}\n"
            "Document Context (if any):\n{rag_context}\n"
            "Uploaded data files available (filename -> full path):\n{data_files}",
        ),
    ]
)
code_executor_agent = code_executor_prompt | llm.with_structured_output(CodeGenOutput)
#-------------------------------Speaker Selector------------------------------------------------
speaker_selector_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompts["speaker_selector"]["prompt"]),
        ("human", "Context: {context}"),
    ]
)
speaker_selector_agent = speaker_selector_prompt | llm.with_structured_output(NextSpeaker)
