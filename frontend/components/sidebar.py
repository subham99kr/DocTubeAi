import streamlit as st
import uuid
from api.history_client import load_history
from api.metadata_client import load_metadata


def render_sidebar():
    with st.sidebar:
        st.title("📁 Chats")

        # ------------------------------
        # SAFETY: initialize everything
        # ------------------------------
        if "session_id" not in st.session_state:
            st.session_state.session_id = str(uuid.uuid4())

        if "messages" not in st.session_state:
            st.session_state.messages = []

        if "pdfs" not in st.session_state:
            st.session_state.pdfs = []

        if "urls" not in st.session_state:
            st.session_state.urls = []

        if "status" not in st.session_state:
            st.session_state.status = None

        # backend sessions (logged in)
        if "sessions" not in st.session_state:
            st.session_state.sessions = []

        # frontend-only sessions (guest)
        if "guest_sessions" not in st.session_state:
            st.session_state.guest_sessions = []

        if "user_status" not in st.session_state:
            st.session_state.user_status = "guest"

        # ------------------------------
        # NEW CHAT (always available)
        # ------------------------------
        if st.button("➕ New Chat", use_container_width=True):
            new_id = str(uuid.uuid4())

            # store guest chats locally
            if st.session_state.user_status != "registered":
                st.session_state.guest_sessions.append(new_id)

            st.session_state.session_id = new_id
            st.session_state.messages = []
            st.session_state.pdfs = []
            st.session_state.urls = []
            st.session_state.status = None
            st.rerun()

        st.divider()

        # ------------------------------
        # HISTORY LIST
        # ------------------------------
        if st.session_state.user_status == "registered":
            sessions = st.session_state.sessions
        else:
            sessions = st.session_state.guest_sessions

        if not sessions:
            st.caption("No previous chats")
            return

        for s in sessions:
            # registered users → dict
            if isinstance(s, dict):
                session_id = s.get("session_id")
                title = s.get("title", "New Chat")
            else:
                # guest users → just session_id
                session_id = s
                title = "New Chat"

            if st.button(
                title,
                key=f"chat_{session_id}",
                use_container_width=True
            ):
                _load_session(session_id)


def _load_session(session_id: str):
    st.session_state.session_id = session_id

    # ------------------------------
    # Load history (safe)
    # ------------------------------
    try:
        st.session_state.messages = load_history(session_id)
    except Exception:
        st.session_state.messages = []

    # ------------------------------
    # Load metadata (safe)
    # ------------------------------
    try:
        meta = load_metadata(session_id)
        st.session_state.pdfs = [
            p for p in meta.get("pdfs_uploaded", [])
            if isinstance(p, str) and p.strip()
        ]
        st.session_state.urls = _dedupe_urls(
            meta.get("url_links", [])
        )
    except Exception:
        st.session_state.pdfs = []
        st.session_state.urls = []

    st.session_state.status = None
    st.rerun()


def _dedupe_urls(urls):
    seen = set()
    out = []
    for u in urls:
        url = u.get("url")
        if url and url not in seen:
            seen.add(url)
            out.append(u)
    return out
