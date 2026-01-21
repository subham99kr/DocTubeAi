import re
import streamlit as st
from modules.handle_url_submit import handle_url_submit

YOUTUBE_REGEX = re.compile(
    r"(https?://)?(www\.)?"
    r"(youtube\.com/watch\?v=|youtu\.be/)"
    r"[\w\-]{11}"
)

def is_youtube_video(url: str) -> bool:
    return bool(YOUTUBE_REGEX.search(url))

def handle_url_click():
    url_val = st.session_state.get("header_url_input", "").strip()

    if not url_val:
        st.toast("⚠️ Enter a URL first")
        return

    if not is_youtube_video(url_val):
        st.toast("❌ Not a valid YouTube video URL")
        return

    handle_url_submit(url_val)

    # ✅ SAFE: widget-clearing inside callback
    st.session_state["header_url_input"] = ""
