"""Pydantic schemas shared across the codebase.

Two groups live here:
  - Agent structured-output schemas, consumed via
    `llm.with_structured_output(...)` in `src/agents/agents.py`.
  - FastAPI request/response DTOs, consumed by `src/routers/*`.
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# --------------------------------------------------------------------------
# Agent structured-output schemas
# --------------------------------------------------------------------------

AgentName = Literal[
    "web_searcher",
    "web_scraper",
    "rag_retriever",
    "research_analyst",
    "answer_refiner",
    "code_executor",
]


class NextSpeaker(BaseModel):
    """The next agent to run in the multi-agent workflow."""
    speaker: Literal[
        "orchestrator",
        "web_searcher",
        "web_scraper",
        "rag_retriever",
        "research_analyst",
        "answer_refiner",
        "code_executor",
        "END",
    ] = Field(description="Name of the next agent to run.")


class CodeGenOutput(BaseModel):
    """Code generation output from the code executor agent."""
    description: str = Field(description="Brief description of what the code does.")
    code: str = Field(description="Complete, self-contained Python code to execute.")


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
            "information is needed. Include 'rag_retriever' ONLY when the "
            "question is about the user's own uploaded sources AND sources "
            "are available for this thread. Include 'research_analyst' "
            "whenever 'web_searcher', 'web_scraper', or 'rag_retriever' is "
            "in the list."
        )
    )


class ScrapeTargets(BaseModel):
    """URLs selected for full-content scraping."""
    urls: List[str] = Field(
        description="Fully-qualified http(s) URLs to fetch and scrape. 1-3 URLs."
    )


# --------------------------------------------------------------------------
# FastAPI request/response DTOs
# --------------------------------------------------------------------------

class ChatRequest(BaseModel):
    prompt: str
    thread_id: Optional[str] = None


class ChatResponse(BaseModel):
    task_id: str


class AnswerResponse(BaseModel):
    status: str  # "Pending" | "Completed" | "Failed"
    result: Optional[dict] = None
    error: Optional[str] = None


class SourceFilePayload(BaseModel):
    filename: str
    content_base64: str


class SourceUploadRequest(BaseModel):
    thread_id: str
    files: List[SourceFilePayload]


class SourceUploadTask(BaseModel):
    filename: str
    task_id: str


class SourceUploadResponse(BaseModel):
    tasks: List[SourceUploadTask]


class SourceInfo(BaseModel):
    source_id: str
    filename: str
    num_chunks: int
    uploaded_at: str


class SourceListResponse(BaseModel):
    sources: List[SourceInfo]


class DeleteSourceResponse(BaseModel):
    deleted: bool


class DataFileUploadRequest(BaseModel):
    thread_id: str
    files: List[SourceFilePayload]


class DataFileInfo(BaseModel):
    filename: str
    size_bytes: int


class DataFilesListResponse(BaseModel):
    files: List[DataFileInfo]


class DeleteDataFileResponse(BaseModel):
    deleted: bool


class SessionInfo(BaseModel):
    thread_id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int


class MessageInfo(BaseModel):
    role: str
    content: str
    code_run_id: str = ""
    code_files: Optional[list] = None
    code_result: str = ""
    message_index: int
