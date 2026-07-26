import base64
import html
import io
import re
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
        "--mac-bg": "#1a1008",
        "--mac-bg-alt": "#221508",
        "--mac-panel": "#2e1e0880",
        "--mac-border": "#4a3018",
        "--mac-violet": "#f97316",
        "--mac-violet-soft": "rgba(249,115,22,0.35)",
        "--mac-violet-dark": "#c2540a",
        "--mac-cyan": "#fbbf24",
        "--mac-cyan-dark": "#b45309",
        "--mac-text": "#fef3e2",
        "--mac-text-dim": "#c49e70",
        "--glow-1": "rgba(249,115,22,0.14)",
        "--glow-2": "rgba(251,191,36,0.09)",
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


def _delete_session(thread_id: str) -> bool:
    try:
        r = requests.delete(f"{API_BASE_URL}/sessions/{thread_id}", timeout=5)
        return r.status_code == 204
    except requests.RequestException:
        return False


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
        _render_banner()
        st.divider()

        # Theme toggle
        _render_theme_toggle()
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
                display_label = (raw_title[:34] + "…") if len(raw_title) > 37 else raw_title
                is_active = session["thread_id"] == st.session_state.thread_id
                tid = session["thread_id"]
                col_title, col_del = st.columns([6, 1], gap="small", vertical_alignment="center")
                with col_title:
                    if st.button(
                        display_label,
                        key=f"session_{tid}",
                        use_container_width=True,
                        type="primary" if is_active else "secondary",
                    ):
                        if not is_active:
                            msgs = _fetch_session_messages(tid)
                            st.session_state.thread_id = tid
                            st.session_state.display_history = [
                                {
                                    "role": m["role"],
                                    "content": m["content"],
                                    "code_run_id": m.get("code_run_id", ""),
                                    "code_files": m.get("code_files") or [],
                                    "code_result": m.get("code_result", ""),
                                    "web_result_cards": m.get("web_result_cards") or [],
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
                with col_del:
                    if st.button("✕", key=f"del_{tid}", help="Delete", use_container_width=True):
                        _delete_session(tid)
                        if is_active:
                            _reset_conversation()
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


def _render_theme_toggle() -> None:
    """Two-button theme toggle rendered inside the sidebar."""
    current = st.session_state.get("theme", THEME_NAMES[0])
    col1, col2 = st.columns(2, gap="small")
    for col, name in zip([col1, col2], THEME_NAMES):
        emoji, label = name.split(" ", 1)
        with col:
            if st.button(
                f"{emoji}  {label}",
                use_container_width=True,
                type="primary" if name == current else "secondary",
                key=f"theme_btn_{name}",
            ):
                st.session_state.theme = name
                st.rerun()


@st.cache_data(show_spinner=False)
def _banner_png_b64(color_hex: str) -> str:
    from PIL import Image, ImageDraw, ImageFont
    import matplotlib

    font_path = matplotlib.get_data_path() + "/fonts/ttf/DejaVuSansMono.ttf"
    h_str = color_hex.lstrip("#")
    fill = (int(h_str[0:2], 16), int(h_str[2:4], 16), int(h_str[4:6], 16), 255)

    lines = BANNER.split("\n")
    font_size = 13
    font = ImageFont.truetype(font_path, font_size)
    line_h = font_size + 3
    dummy = Image.new("RGBA", (1, 1))
    draw = ImageDraw.Draw(dummy)
    max_w = max((draw.textlength(ln, font=font) for ln in lines), default=0)
    w, h = int(max_w) + 4, line_h * len(lines) + 4
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for i, line in enumerate(lines):
        draw.text((2, 2 + i * line_h), line, font=font, fill=fill)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _render_banner() -> None:
    theme = st.session_state.get("theme", THEME_NAMES[0])
    color_hex = THEMES[theme]["--mac-violet"]
    b64 = _banner_png_b64(color_hex)
    st.markdown(
        f'<div class="mac-banner-wrap">'
        f'<img class="mac-banner-img" src="data:image/png;base64,{b64}" alt="Multi-Agent Chatbot"/>'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_web_results(cards: list) -> None:
    """Render web search result cards with favicon, title, snippet, and link."""
    if not cards:
        return
    card_html_parts = []
    for c in cards:
        title = c.get("title", "").replace("<", "&lt;").replace(">", "&gt;")
        url = c.get("url", "")
        snippet = c.get("snippet", "").replace("<", "&lt;").replace(">", "&gt;")
        favicon = c.get("favicon_url", "")
        try:
            from urllib.parse import urlparse
            display_domain = urlparse(url).netloc
        except Exception:
            display_domain = url
        favicon_img = (
            f'<img src="{favicon}" class="web-card-favicon" onerror="this.style.display=\'none\'">'
            if favicon else ""
        )
        card_html_parts.append(
            f"""<a href="{url}" target="_blank" rel="noopener noreferrer" class="web-card">
  <div class="web-card-header">
    {favicon_img}
    <span class="web-card-domain">{display_domain}</span>
  </div>
  <div class="web-card-title">{title}</div>
  <div class="web-card-snippet">{snippet}</div>
</a>"""
        )
    cards_html = "\n".join(card_html_parts)
    st.markdown(
        f'<div class="web-results-label">Web sources</div>'
        f'<div class="web-results-grid">{cards_html}</div>',
        unsafe_allow_html=True,
    )


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


def _clean_content(content: str, has_web_cards: bool) -> str:
    """Strip the trailing 'Sources:' block when structured web cards are shown."""
    if not has_web_cards:
        return content
    cleaned = re.sub(
        r"\n{0,2}\*{0,2}Sources?\*{0,2}:[\s\S]*$",
        "",
        content,
        flags=re.IGNORECASE,
    ).rstrip()
    return cleaned if cleaned else content


def _render_history() -> None:
    for message in st.session_state.display_history:
        with st.chat_message(message["role"]):
            has_cards = bool(message.get("web_result_cards"))
            content = _clean_content(message["content"], has_cards)
            st.markdown(content)
            if message["role"] == "assistant":
                _render_web_results(message.get("web_result_cards", []))
                if message.get("code_run_id"):
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
            "web_result_cards": payload.get("web_result_cards", []),
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
