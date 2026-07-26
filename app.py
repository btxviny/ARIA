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
from ui.display_utils.sources import render_file_strip

# ---------------------------------------------------------------------------
# Theme definitions — CSS variable overrides injected at runtime
# ---------------------------------------------------------------------------
THEMES: dict[str, dict[str, str]] = {
    "🧛 Dracula": {
        "--mac-bg": "#0b0b14",
        "--mac-bg-alt": "#12121f",
        "--mac-panel": "#15152680",
        "--mac-border": "#2a2a45",
        "--mac-violet": "#a259ff",
        "--mac-violet-soft": "rgba(162,89,255,0.35)",
        "--mac-violet-dark": "#6b2fd6",
        "--mac-cyan": "#47e0d1",
        "--mac-cyan-dark": "#1d8f85",
        "--mac-text": "#e7e6f5",
        "--mac-text-dim": "#9490b3",
        "--glow-1": "rgba(162,89,255,0.16)",
        "--glow-2": "rgba(71,224,209,0.10)",
    },
    "🍪 Cookie": {
        "--mac-bg": "#1c1c1c",
        "--mac-bg-alt": "#242424",
        "--mac-panel": "#2e2e2e80",
        "--mac-border": "#3d3d3d",
        "--mac-violet": "#f97316",
        "--mac-violet-soft": "rgba(249,115,22,0.35)",
        "--mac-violet-dark": "#ea580c",
        "--mac-cyan": "#fb923c",
        "--mac-cyan-dark": "#c2660a",
        "--mac-text": "#f5f0eb",
        "--mac-text-dim": "#a39e98",
        "--glow-1": "rgba(249,115,22,0.12)",
        "--glow-2": "rgba(251,146,60,0.08)",
    },
}

THEME_NAMES = list(THEMES.keys())


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


SESSIONS_PAGE_SIZE = 50


@st.cache_data(ttl=30)
def _fetch_sessions(limit: int = SESSIONS_PAGE_SIZE) -> list[dict]:
    """Fetch session list from the API, cached for 30 s across all browser tabs."""
    try:
        r = requests.get(f"{API_BASE_URL}/sessions", params={"limit": limit}, timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return []


def _fetch_session_messages(thread_id: str) -> list[dict]:
    try:
        r = requests.get(f"{API_BASE_URL}/sessions/{thread_id}/messages", timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.RequestException:
        return []


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
        "waiting_for_response": False,
        "uploaded_signatures": set(),
        "request_started_at": None,
        "theme": THEME_NAMES[0],
        "sessions_limit": SESSIONS_PAGE_SIZE,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _reset_conversation() -> None:
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.display_history = []
    st.session_state.task_id = None
    st.session_state.waiting_for_response = False
    st.session_state.request_started_at = None
    # Clear sidebar file-cache so it doesn't show the previous thread's uploads.
    st.session_state.uploaded_signatures = set()
    st.session_state.data_files_cache = {}
    _fetch_sessions.clear()


# --- UI ---------------------------------------------------------------------
def _render_sidebar() -> None:
    with st.sidebar:
        st.title("Multi-Agent Chatbot")
        st.caption(SUBTITLE)
        st.divider()
        if st.button("＋  New conversation", use_container_width=True):
            _reset_conversation()
            st.rerun()

        # ---- Past conversations ------------------------------------------------
        st.divider()
        st.markdown("**Conversations**")
        past_sessions = _fetch_sessions(st.session_state.sessions_limit)
        if not past_sessions:
            st.caption("No saved conversations yet.")
        else:
            for session in past_sessions:
                raw_title = session.get("title") or "Untitled"
                display_label = (raw_title[:40] + "…") if len(raw_title) > 43 else raw_title
                is_active = session["thread_id"] == st.session_state.thread_id
                if st.button(
                    display_label,
                    key=f"session_{session['thread_id']}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary",
                ):
                    if not is_active:
                        # Loading a past session restores display_history for
                        # display only. LangGraph MemorySaver state is not
                        # restored, so the next question starts with fresh context.
                        msgs = _fetch_session_messages(session["thread_id"])
                        st.session_state.thread_id = session["thread_id"]
                        st.session_state.display_history = [
                            {
                                "role": m["role"],
                                "content": m["content"],
                                "code_run_id": m.get("code_run_id", ""),
                                "code_files": m.get("code_files") or [],
                                "code_result": m.get("code_result", ""),
                            }
                            for m in msgs
                        ]
                        st.session_state.task_id = None
                        st.session_state.waiting_for_response = False
                        st.session_state.request_started_at = None
                        st.session_state.uploaded_signatures = set()
                        st.session_state.data_files_cache = {}
                        _fetch_sessions.clear()
                        st.rerun()

            if len(past_sessions) >= st.session_state.sessions_limit:
                if st.button("Load more", use_container_width=True, key="load_more_sessions"):
                    st.session_state.sessions_limit += SESSIONS_PAGE_SIZE
                    _fetch_sessions.clear()
                    st.rerun()
        # -----------------------------------------------------------------------



def _inject_theme() -> None:
    theme_vars = THEMES[st.session_state.get("theme", THEME_NAMES[0])]
    vars_css = ":root {" + "".join(f"{k}:{v};" for k, v in theme_vars.items()) + "}"
    st.markdown(f"<style>{vars_css}</style>", unsafe_allow_html=True)


def _render_theme_bar() -> None:
    """Compact emoji theme switcher pinned to the top-right of the content area."""
    _, right = st.columns([9, 1])
    with right:
        btn_cols = st.columns(len(THEMES))
        for i, name in enumerate(THEME_NAMES):
            with btn_cols[i]:
                st.button(
                    name.split()[0],          # just the emoji
                    key=f"theme_btn_{i}",
                    help=name.split(maxsplit=1)[-1],  # tooltip shows the name
                    type="primary" if st.session_state.theme == name else "secondary",
                    use_container_width=True,
                    on_click=_set_theme,
                    args=(name,),
                )


def _set_theme(name: str) -> None:
    st.session_state.theme = name


def _render_banner() -> None:
    _, mid, _ = st.columns([1, 10, 1])
    with mid:
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
    _inject_theme()
    _render_sidebar()
    _render_theme_bar()

    _render_banner()

    _render_history()

    render_file_strip(st.session_state.thread_id)

    user_input = st.chat_input(
        "Ask me anything...",
        disabled=st.session_state.waiting_for_response,
    )

    if user_input and not st.session_state.waiting_for_response:
        st.session_state.display_history.append({"role": "user", "content": user_input})
        task_id = post_question(user_input, st.session_state.thread_id)
        if task_id:
            st.session_state.task_id = task_id
            st.session_state.waiting_for_response = True
        st.rerun()

    if st.session_state.task_id and st.session_state.waiting_for_response:
        _handle_response()


if __name__ == "__main__":
    main()
