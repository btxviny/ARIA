"""Embeddings configuration.

The active embedding model is selected by uncommenting exactly one block
below, mirroring the LLM toggle in `llm.py`. Default is a local, open-source
HuggingFace model (sentence-transformers) -- no API key, no external calls
at query time. Its weights are pre-baked into the Docker image at build time
(see Dockerfile) so there's no first-request download stall.

NOTE: switching embedding models changes the vector space and (usually) the
dimensionality. Existing Chroma collections embedded with a different model
are not compatible -- wipe the `chroma-data` volume (or delete the affected
per-thread collections) after changing this file.

Environment variables honored:
  OLLAMA_BASE_URL  default http://localhost:11434
  OPENAI_API_KEY   required when using the OpenAIEmbeddings block.
"""
import os

import dotenv
import httpx
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import OllamaEmbeddings
from langchain_openai import OpenAIEmbeddings

dotenv.load_dotenv()

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")


# --- HuggingFace (local, open-source, default) ---
embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2",
)

# --- Ollama (local) ---
# embeddings = OllamaEmbeddings(
#     model="nomic-embed-text",
#     base_url=OLLAMA_BASE_URL,
# )

# --- OpenAI (cloud) ---
# embeddings = OpenAIEmbeddings(
#     api_key=os.environ["OPENAI_API_KEY"],
#     model="text-embedding-3-small",
#     http_client=httpx.Client(verify=False),
# )
