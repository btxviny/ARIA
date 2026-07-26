import base64
import html
import io
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
    "🌊 Ocean": {
        "--mac-bg": "#060d1a",
        "--mac-bg-alt": "#0a1628",
        "--mac-panel": "#0d1f3880",
        "--mac-border": "#1a3a5c",
        "--mac-violet": "#38bdf8",
        "--mac-violet-soft": "rgba(56,189,248,0.30)",
        "--mac-violet-dark": "#0369a1",
        "--mac-cyan": "#67e8f9",
        "--mac-cyan-dark": "#0891b2",
        "--mac-text": "#e0f2fe",
        "--mac-text-dim": "#7cb9d8",
        "--glow-1": "rgba(56,189,248,0.14)",
        "--glow-2": "rgba(103,232,249,0.09)",
    },
    "🌲 Forest": {
        "--mac-bg": "#080f08",
        "--mac-bg-alt": "#0d160d",
        "--mac-panel": "#11201180",
        "--mac-border": "#1e3a1e",
        "--mac-violet": "#4ade80",
        "--mac-violet-soft": "rgba(74,222,128,0.30)",
        "--mac-violet-dark": "#16a34a",
        "--mac-cyan": "#86efac",
        "--mac-cyan-dark": "#15803d",
        "--mac-text": "#dcfce7",
        "--mac-text-dim": "#6dbd8a",
        "--glow-1": "rgba(74,222,128,0.14)",
        "--glow-2": "rgba(134,239,172,0.09)",
    },
    "🌸 Sakura": {
        "--mac-bg": "#130a10",
        "--mac-bg-alt": "#1e0f1a",
        "--mac-panel": "#27132180",
        "--mac-border": "#4a1e38",
        "--mac-violet": "#f472b6",
        "--mac-violet-soft": "rgba(244,114,182,0.32)",
        "--mac-violet-dark": "#be185d",
        "--mac-cyan": "#fb7185",
        "--mac-cyan-dark": "#be123c",
        "--mac-text": "#fce7f3",
        "--mac-text-dim": "#c4789e",
        "--glow-1": "rgba(244,114,182,0.15)",
        "--glow-2": "rgba(251,113,133,0.09)",
    },
    "🔥 Inferno": {
        "--mac-bg": "#0f0500",
        "--mac-bg-alt": "#1a0a00",
        "--mac-panel": "#251000",
        "--mac-border": "#4a1e00",
        "--mac-violet": "#f97316",
        "--mac-violet-soft": "rgba(249,115,22,0.32)",
        "--mac-violet-dark": "#c2410c",
        "--mac-cyan": "#fbbf24",
        "--mac-cyan-dark": "#b45309",
        "--mac-text": "#fff7ed",
        "--mac-text-dim": "#c48a50",
        "--glow-1": "rgba(249,115,22,0.16)",
        "--glow-2": "rgba(251,191,36,0.10)",
    },
    "💚 Matrix": {
        "--mac-bg": "#000500",
        "--mac-bg-alt": "#000d00",
        "--mac-panel": "#00140080",
        "--mac-border": "#003300",
        "--mac-violet": "#00ff41",
        "--mac-violet-soft": "rgba(0,255,65,0.25)",
        "--mac-violet-dark": "#00a629",
        "--mac-cyan": "#00cc33",
        "--mac-cyan-dark": "#007a1f",
        "--mac-text": "#ccffcc",
        "--mac-text-dim": "#4d994d",
        "--glow-1": "rgba(0,255,65,0.12)",
        "--glow-2": "rgba(0,204,51,0.08)",
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
        st.title("Multi-Agent Chatbot")
        st.caption(SUBTITLE)
        st.divider()
        if st.button("＋  New conversation", use_container_width=True):
            _reset_conversation()
            st.rerun()

        # ---- Past conversations ------------------------------------------------
        st.divider()
        st.markdown("**Conversations**")
        # Style the 🗑 delete buttons as small dim icons
        st.markdown("""
<style>
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:has(p:empty),
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] p:only-child {
    all: unset;
}
</style>
<script>
(function() {
    function styleTrashBtns() {
        document.querySelectorAll('[data-testid="stSidebar"] button').forEach(btn => {
            if (btn.textContent.trim() === '🗑') {
                btn.classList.add('mac-trash-btn');
            }
        });
    }
    const ob = new MutationObserver(styleTrashBtns);
    ob.observe(document.body, {childList: true, subtree: true});
    styleTrashBtns();
})();
</script>
<style>
.mac-trash-btn {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 4px !important;
    min-height: 0 !important;
    font-size: 14px !important;
    opacity: 0.45 !important;
    transition: opacity 0.15s ease, color 0.15s ease !important;
    width: 28px !important;
    color: var(--mac-text-dim) !important;
}
.mac-trash-btn:hover {
    opacity: 1 !important;
    color: #ff5555 !important;
    transform: none !important;
    box-shadow: none !important;
}
</style>
""", unsafe_allow_html=True)
        past_sessions = _fetch_sessions(st.session_state.sessions_limit)
        if not past_sessions:
            st.caption("No saved conversations yet.")
        else:
            for session in past_sessions:
                raw_title = session.get("title") or "Untitled"
                display_label = (raw_title[:35] + "…") if len(raw_title) > 38 else raw_title
                is_active = session["thread_id"] == st.session_state.thread_id
                tid = session["thread_id"]
                col_title, col_del = st.columns([5, 1])
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
                    if st.button("🗑", key=f"del_{tid}", help="Delete this conversation"):
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


def _render_theme_picker() -> None:
    """Centered circle-group theme switcher rendered in the main area."""
    current = st.session_state.get("theme", THEME_NAMES[0])

    per_swatch_css = "\n".join(
        f'[data-testid="stRadioGroup"] label[data-testid="stRadioOption"]:nth-child({i + 1}) '
        f'{{ border-color: {v["--mac-violet"]} !important; '
        f'background: {v["--mac-violet"]}33 !important; }}\n'
        f'[data-testid="stRadioGroup"] label[data-testid="stRadioOption"]:nth-child({i + 1}) p '
        f'{{ color: {v["--mac-violet"]} !important; }}'
        for i, v in enumerate(THEMES.values())
    )
    active_css = "\n".join(
        f'[data-testid="stRadioGroup"] label[data-testid="stRadioOption"]:nth-child({i + 1})[data-selected="true"] '
        f'{{ background: {v["--mac-violet"]} !important; '
        f'box-shadow: 0 0 8px {v["--mac-violet"]}66 !important; }}\n'
        f'[data-testid="stRadioGroup"] label[data-testid="stRadioOption"]:nth-child({i + 1})[data-selected="true"] p '
        f'{{ color: #fff !important; }}'
        for i, v in enumerate(THEMES.values())
    )
    base_css = """
    /* Hide the radio widget label */
    [data-testid="stRadio"] > label { display: none !important; }
    /* Remove Streamlit focus outline */
    [data-testid="stRadioGroup"] label[data-testid="stRadioOption"]:focus-within,
    [data-testid="stRadioGroup"] label[data-testid="stRadioOption"]:focus {
        outline: none !important;
        box-shadow: inherit !important;
    }
    /* Unified circle-group container */
    [data-testid="stRadioGroup"] {
        flex-direction: row !important;
        gap: 5px !important;
        background: rgba(255,255,255,0.05) !important;
        border-radius: 30px !important;
        padding: 5px 7px !important;
        flex-wrap: nowrap !important;
    }
    /* Each option as a circle */
    [data-testid="stRadioGroup"] label[data-testid="stRadioOption"] {
        padding: 0 !important;
        margin: 0 !important;
        width: 34px !important;
        height: 34px !important;
        min-width: 34px !important;
        min-height: 34px !important;
        max-width: 34px !important;
        max-height: 34px !important;
        border-radius: 50% !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        cursor: pointer !important;
        border: 2px solid transparent !important;
        transition: all 0.15s ease !important;
    }
    /* Wrapper divs: flatten to flex center */
    [data-testid="stRadioGroup"] label[data-testid="stRadioOption"] > div {
        display: contents !important;
    }
    [data-testid="stRadioGroup"] label[data-testid="stRadioOption"] > div > div {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 0 !important;
    }
    /* Hide the radio dot indicator */
    [data-testid="stRadioGroup"] label[data-testid="stRadioOption"] > div > div > div:first-child {
        display: none !important;
    }
    /* Emoji text */
    [data-testid="stRadioGroup"] label[data-testid="stRadioOption"] p {
        margin: 0 !important;
        padding: 0 !important;
        font-size: 18px !important;
        line-height: 1 !important;
    }
    """
    st.markdown(f"<style>{base_css}\n{per_swatch_css}\n{active_css}</style>", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        choice = st.radio(
            "Theme",
            options=THEME_NAMES,
            index=THEME_NAMES.index(current),
            format_func=lambda n: n.split()[0],
            horizontal=True,
            label_visibility="collapsed",
            key="theme_radio",
        )
    if choice and choice != current:
        st.session_state.theme = choice
        st.rerun()


def _set_theme(name: str) -> None:
    st.session_state.theme = name


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


def _render_history() -> None:
    for message in st.session_state.display_history:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
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
    _render_theme_picker()

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
