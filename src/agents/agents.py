import dotenv
import yaml

from src.agents.llm import llm
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
orchestrator_agent = orchestrator_prompt | llm | StrOutputParser()
#-------------------------------Web Searcher------------------------------------------------------]
web_searcher_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompts["web_searcher"]["prompt"]),
        ("human", "Question: {question}\nOrchestrator's Plan: {plan}"),
    ]
)
web_searcher_agent = web_searcher_prompt | llm | StrOutputParser()
#-------------------------------Research Analyst--------------------------------------------------]
research_analyst_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompts["research_analyst"]["prompt"]),
        ("human", "Question: {question}\nSearch Results:\n{search_results}"),
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
speaker_selector_agent = speaker_selector_prompt | llm | StrOutputParser()
