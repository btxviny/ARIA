import os
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
import dotenv
import httpx
dotenv.load_dotenv()

# --- Ollama (local) ---
# llm = ChatOllama(
#     model="gemma3:4b",
#     temperature=0.1,
# )

# --- OpenAI (cloud) ---
llm = ChatOpenAI(
    api_key=os.environ['OPENAI_API_KEY'],
    model='gpt-4o',
    http_client=httpx.Client(verify=False),
)