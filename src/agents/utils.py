import os
import ssl
from typing import get_args

import urllib3
import urllib3.util.ssl_
from langchain_core.messages import AIMessage, HumanMessage

from src.schemas import AgentName


def format_history(messages: list, summary: str = "") -> str:
    formated_history = []
    if summary:
        formated_history.append(f"[Summary of earlier conversation]\n{summary}")
    for message in messages:
        if isinstance(message, HumanMessage):
            formated_history.append(f"User: {message.content}")
        elif isinstance(message, AIMessage):
            formated_history.append(f"Assistant: {message.content}")
    return "\n".join(formated_history)

def create_urllib3_context_no_verify(*args, **kwargs):
        context = urllib3.util.ssl_.create_urllib3_context_original(*args, **kwargs)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
    

def init_ssl_context():
    """Disable SSL verification for requests (needed for corporate proxies)."""
    os.environ['REQUESTS_CA_BUNDLE'] = ''
    os.environ['CURL_CA_BUNDLE'] = ''
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    urllib3.util.ssl_.create_urllib3_context_original = urllib3.util.ssl_.create_urllib3_context
    urllib3.util.ssl_.create_urllib3_context = create_urllib3_context_no_verify


def dedup_urls(urls: list[str]) -> list[str]:
    """Remove duplicates while preserving order."""
    seen = set()
    out = []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


VALID_PIPELINE_AGENTS = set(get_args(AgentName))
