import time
import uuid

import requests
import streamlit as st

from src.banner import BANNER, SUBTITLE
from src.config import (
    API_BASE_URL,
    RESPONSE_POLL_INTERVAL,
    RESPONSE_TIMEOUT_SECONDS,
)
from ui.display_utils.utils import sample_questions


# --- API client -------------------------------------------------------------
def post_question(prompt: str, thread_id: str) -> str | None:
    try:
        r = requests.post(
            f"{API_BASE_URL}/question/",
            json={"prompt": prompt, "thread_id": thread_id},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("task_id")
    except requests.RequestException as e:
        st.error(f"Failed to reach API: {e}")
        return None


def get_answer(task_id: str) -> dict:
    try:
        r = requests.get(f"{API_BASE_URL}/answer/{task_id}", timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        return {"status": "Failed", "error": str(e)}


def stream_answer(answer: str):
    for word in answer.split(" "):
        yield word + " "
        time.sleep(0.02)


# --- Session state helpers --------------------------------------------------
def _init_session_state() -> None:
    defaults = {
        "thread_id": str(uuid.uuid4()),
        "task_id": None,
        "display_history": [],
        "selected_question": None,
        "waiting_for_response": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _reset_conversation() -> None:
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.display_history = []
    st.session_state.task_id = None
    st.session_state.selected_question = None
    st.session_state.waiting_for_response = False


# --- UI ---------------------------------------------------------------------
def _render_sidebar() -> None:
    with st.sidebar:
        st.title("Multi-Agent Chatbot")
        st.caption(SUBTITLE)
        st.divider()
        st.markdown("**Session**")
        st.code(st.session_state.thread_id, language=None)
        if st.button("New conversation", use_container_width=True):
            _reset_conversation()
            st.rerun()
        st.divider()
        with st.expander("API status"):
            try:
                r = requests.get(f"{API_BASE_URL}/health", timeout=2)
                if r.ok:
                    st.success(f"Connected to {API_BASE_URL}")
                else:
                    st.error(f"API returned {r.status_code}")
            except requests.RequestException:
                st.error(f"Cannot reach {API_BASE_URL}")


def _render_banner() -> None:
    st.markdown(
        f"""
        <pre style="
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 11px;
            line-height: 1.1;
            overflow-x: auto;
            color: #8be9fd;
            background: transparent;
            margin: 0 0 16px 0;
            padding: 0;
        ">{BANNER}</pre>
        """,
        unsafe_allow_html=True,
    )


def _render_history() -> None:
    for message in st.session_state.display_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])


def _handle_response() -> None:
    """Poll the API until the task finishes or times out."""
    status_placeholder = st.empty()
    start = time.time()
    result: dict = {"status": "Pending"}

    while time.time() - start < RESPONSE_TIMEOUT_SECONDS:
        result = get_answer(st.session_state.task_id)
        status = result.get("status")
        if status == "Completed":
            break
        if status == "Failed":
            break
        elapsed = int(time.time() - start)
        status_placeholder.caption(f"Thinking... ({elapsed}s)")
        time.sleep(RESPONSE_POLL_INTERVAL)

    status_placeholder.empty()

    status = result.get("status")
    if status == "Completed" and result.get("result", {}).get("answer"):
        answer = result["result"]["answer"]
        with st.chat_message("assistant"):
            st.write_stream(stream_answer(answer))
        st.session_state.display_history.append({"role": "assistant", "content": answer})
    elif status == "Failed":
        err = result.get("error", "Unknown error")
        st.error(f"Agent failed: {err}")
    else:
        st.error("The response generation took too long. Please try again.")

    st.session_state.task_id = None
    st.session_state.waiting_for_response = False


def main() -> None:
    st.set_page_config(
        page_title="Multi-Agent Chatbot",
        page_icon=":robot_face:",
        layout="wide",
    )

    with open("ui/style.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

    _init_session_state()
    _render_sidebar()

    _render_banner()

    selected = sample_questions()
    if selected:
        st.session_state.selected_question = selected

    _render_history()

    user_input = (
        st.chat_input(
            "Ask me anything...",
            disabled=st.session_state.waiting_for_response,
        )
        or st.session_state.selected_question
    )

    if user_input and not st.session_state.waiting_for_response:
        st.session_state.display_history.append({"role": "user", "content": user_input})
        st.session_state.selected_question = None
        task_id = post_question(user_input, st.session_state.thread_id)
        if task_id:
            st.session_state.task_id = task_id
            st.session_state.waiting_for_response = True
        st.rerun()

    if st.session_state.task_id and st.session_state.waiting_for_response:
        _handle_response()
        st.rerun()


if __name__ == "__main__":
    main()
