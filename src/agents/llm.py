"""LLM configuration.

The active LLM is selected by uncommenting exactly one block below.

Environment variables honored:
  OLLAMA_BASE_URL  default http://localhost:11434
                   set to http://host.docker.internal:11434 when running in
                   Docker on Windows/macOS so the container can reach the
                   native Ollama server running on the host.
  OPENAI_API_KEY   required when using the ChatOpenAI block.
"""
import os

import dotenv
import httpx
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

dotenv.load_dotenv()

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


# --- Ollama (local) ---
# llm = ChatOllama(
#     model="llama3.1:8b",
#     temperature=0.1,
#     base_url=OLLAMA_BASE_URL,
# )

#--- OpenAI (cloud) ---
llm = ChatOpenAI(
    api_key=os.environ["OPENAI_API_KEY"],
    #model="gpt-4o-mini",
    model="gpt-5.4-mini",
    http_client=httpx.Client(verify=False),
)
