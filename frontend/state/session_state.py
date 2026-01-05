import streamlit as st
import uuid

def init_state():
    # Core chat state
    if "current_session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "current_session_title" not in st.session_state:
        st.session_state.current_session_title = "New Chat"

    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Auth / user
    if "auth_token" not in st.session_state:
        st.session_state.auth_token = None

    if "user_status" not in st.session_state:
        st.session_state.user_status = "guest"

    # this is the loaded session from the db should have all sessions as {session_id,title,last_updated}
    if "sessions" not in st.session_state:
        st.session_state.sessions = []
    
    if "pdfs" not in st.session_state:
        st.session_state.pdfs = []

    # urls as {url,title}
    if "urls" not in st.session_state:
        st.session_state.urls = []

    # UI helpers
    if "status" not in st.session_state:
        st.session_state.status = None
