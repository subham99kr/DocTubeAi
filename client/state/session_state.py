import streamlit as st
import uuid


def initialize_session():
    
    # --- AUTH ---
    st.session_state.setdefault("access_token", None)
    st.session_state.setdefault("user", None)
    st.session_state.setdefault("user_status", "guest")
    st.session_state.setdefault("history_synced", False)

    # --- SESSION ---
    st.session_state.setdefault("session_id", str(uuid.uuid4()))
    st.session_state.setdefault("active_session_id", st.session_state.session_id)
    st.session_state.setdefault("title", "🐣 Welcome !")

    # --- UPLOAD CONTROL ---
    st.session_state.setdefault("uploader_key", 0)
    st.session_state.setdefault("uploaded_once", False)
    st.session_state.setdefault("processing", False)

    # --- DATA ---
    st.session_state.setdefault("sessions", [])
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("uploaded_pdfs", [])
    st.session_state.setdefault("urls", [])

    # --- UI ---
    st.session_state.setdefault("status", None)
    st.session_state.setdefault("current_url", "")
    st.session_state.setdefault("run_chat_once", False)
