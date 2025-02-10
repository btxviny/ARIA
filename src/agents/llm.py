import os
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
import dotenv
dotenv.load_dotenv()

'''llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash-lite-preview-02-05",
    temperature=0.1,
    max_tokens=None,
    timeout=None,
    max_retries=2
)'''

llm = ChatOpenAI(
        api_key = os.environ['OPENAI_API_KEY'],
        model ='gpt-4o-mini'
)