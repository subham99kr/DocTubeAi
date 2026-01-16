import streamlit as st
import uuid

def initialize_session():
    """Initializes all session state keys for a robust production app."""
    
    # --- AUTH & SYNC ---
    if "access_token" not in st.session_state:
        st.session_state.access_token = None 
    if "user" not in st.session_state:
        st.session_state.user = None 
    if "user_status" not in st.session_state:
        st.session_state.user_status = "guest"
    if "history_synced" not in st.session_state:
        st.session_state.history_synced = False

    # --- SESSION IDENTITY ---
    if "session_id" not in st.session_state:
        # Unique ID for the current interaction
        st.session_state.session_id = str(uuid.uuid4())
    if "active_session_id" not in st.session_state:
        # Track which historical session is currently being viewed
        st.session_state.active_session_id = st.session_state.session_id 
    if "title" not in st.session_state:
        st.session_state.title = "🐣 Welcome !"
    if "uploader_key" not in st.session_state:
        st.session_state.uploader_key = 0

    # --- DATA LISTS ---
    if "sessions" not in st.session_state:
        # The list of past chats for the sidebar
        st.session_state.sessions = []
    if "messages" not in st.session_state:
        # Current chat history
        st.session_state.messages = []
    if "uploaded_pdfs" not in st.session_state:
        st.session_state.uploaded_pdfs = []
    if "urls" not in st.session_state:
        # Just the titles for the UI
        st.session_state.urls = []

    # --- UI & FLOW CONTROL ---
    if "status" not in st.session_state:
        st.session_state.status = None
    if "processing" not in st.session_state:
        # Global spinner/loading state
        st.session_state.processing = False
    if "current_url" not in st.session_state:
        # For clearing the URL text input
        st.session_state.current_url = ""

    if "run_chat_once" not in st.session_state:
        st.session_state.run_chat_once = False
