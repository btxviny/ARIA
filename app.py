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
from ui.display_utils.sources import render_sources_sidebar
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


# --- Session state helpers --------------------------------------------------
def _init_session_state() -> None:
    defaults = {
        "thread_id": str(uuid.uuid4()),
        "task_id": None,
        "display_history": [],
        "selected_question": None,
        "waiting_for_response": False,
        "uploaded_signatures": set(),
        "request_started_at": None,
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
    st.session_state.request_started_at = None
    # The new thread_id's Chroma collection doesn't exist yet, so sources
    # are already gone server-side; this just clears the sidebar's local
    # cache of what to display so it doesn't keep showing the old thread's
    # uploads (same reason display_history is cleared above).
    st.session_state.uploaded_signatures = set()
    st.session_state.data_files_cache = {}


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
        render_sources_sidebar(st.session_state.thread_id)
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
    st.code(BANNER, language=None)


def _render_code_outputs(code_result: str, code_files: list, code_run_id: str) -> None:
    """Render code execution output: stdout block + file previews/downloads."""
    if code_result:
        with st.expander("Code execution output", expanded=False):
            st.code(code_result, language=None)

    for file_info in code_files:
        filename = file_info["filename"]
        mime_type = file_info.get("mime_type", "application/octet-stream")
        file_url = f"{API_BASE_URL}/files/{code_run_id}/{filename}"
        try:
            resp = requests.get(file_url, timeout=15)
            resp.raise_for_status()
            file_bytes = resp.content
        except requests.RequestException:
            st.warning(f"Could not load file: {filename}")
            continue

        if mime_type and mime_type.startswith("image/"):
            st.image(file_bytes, caption=filename, width=550)
        else:
            st.download_button(
                label=f"Download {filename}",
                data=file_bytes,
                file_name=filename,
                mime=mime_type,
            )


def _render_history() -> None:
    for message in st.session_state.display_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and message.get("code_run_id"):
                _render_code_outputs(
                    message.get("code_result", ""),
                    message.get("code_files", []),
                    message["code_run_id"],
                )


@st.fragment(run_every=RESPONSE_POLL_INTERVAL)
def _handle_response() -> None:
    """Poll the API once per fragment tick instead of blocking the whole
    script (and thus the whole page) for the entire agent turn. Only this
    fragment reruns every tick -- the sidebar, banner, and history don't."""
    if not (st.session_state.task_id and st.session_state.waiting_for_response):
        return

    if st.session_state.request_started_at is None:
        st.session_state.request_started_at = time.time()
    elapsed = int(time.time() - st.session_state.request_started_at)

    if elapsed >= RESPONSE_TIMEOUT_SECONDS:
        st.error("The response generation took too long. Please try again.")
        st.session_state.task_id = None
        st.session_state.waiting_for_response = False
        st.session_state.request_started_at = None
        st.rerun()
        return

    result = get_answer(st.session_state.task_id)
    status = result.get("status")

    if status == "Completed" and result.get("result", {}).get("answer"):
        payload = result["result"]
        entry = {
            "role": "assistant",
            "content": payload["answer"],
            "code_files": payload.get("code_files", []),
            "code_run_id": payload.get("code_run_id", ""),
            "code_result": payload.get("code_result", ""),
        }
        st.session_state.display_history.append(entry)
        st.session_state.task_id = None
        st.session_state.waiting_for_response = False
        st.session_state.request_started_at = None
        st.rerun()
    elif status == "Failed":
        err = result.get("error", "Unknown error")
        st.error(f"Agent failed: {err}")
        st.session_state.task_id = None
        st.session_state.waiting_for_response = False
        st.session_state.request_started_at = None
    else:
        st.markdown(
            """
            <div class="mac-thinking">
                <div class="mac-ring"></div>
                <span class="mac-label">Generating response
                    <span class="mac-dots"><span>.</span><span>.</span><span>.</span></span>
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )


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


if __name__ == "__main__":
    main()
