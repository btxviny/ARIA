import dotenv
import yaml

from pydantic import BaseModel, Field
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
#-------------------------------SQLAgent-------------------------------------------------------------]
sql_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompts["sql_agent"]["prompt"]),
        ("human", "Context: {context}"),
    ]
)
sql_agent = sql_prompt | llm | StrOutputParser()
#-------------------------------VisualizationAgent------------------------------------------------]
class VisualizationOutput(BaseModel):
    script: str = Field(
        description="The script to generate the visualization."
    )
    file_name: str = Field(
        description="The name of the file where the visualization is stored."
    )
visualization_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", prompts["visualization_agent"]["prompt"]),
        ("human", "Context: {context}"),
    ]
)
visualization_agent = visualization_prompt | llm.with_structured_output(VisualizationOutput)
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

