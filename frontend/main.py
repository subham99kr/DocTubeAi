import streamlit as st

from state.session_state import init_state
from api.home_client import load_home
from api.chat_client import ask_chat

from components.sidebar import render_sidebar
from components.chat_window import render_chat
from components.context_panel import render_context
from components.status_bar import render_status

st.set_page_config(page_title="DocTubeAI", layout="wide")
init_state()

# --- Home init
# Home init
if not st.session_state.sessions:
    try:
        home = load_home(st.session_state.auth_token)
        st.session_state.sessions = home.get("history", [])
        st.session_state.user_status = home.get("user_status", "guest")
    except Exception:
        st.session_state.sessions = []
        st.session_state.user_status = "guest"


# --- Layout
render_sidebar()

left, right = st.columns([3, 1])

with left:
    render_status()
    render_chat()

with right:
    render_context()

# --- Chat input
if prompt := st.chat_input("Ask or paste code…"):
    st.session_state.messages.append({
        "role": "user",
        "content": prompt
    })

    st.session_state.status = "Thinking…"

    with st.spinner("Thinking..."):
        result = ask_chat(
            prompt,
            st.session_state.session_id,
            st.session_state.get("auth_token")
        )

    answer = result.get("answer", "No response")

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer
    })

    st.session_state.status = None
    st.rerun()
