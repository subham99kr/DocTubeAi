import streamlit as st
import uuid
from api.auth_client import render_login
from api.home_client import load_home
from modules.switch_session import switch_session 

def render_sidebar():
    token = st.session_state.get("access_token")
    user = st.session_state.get("user")

    with st.sidebar:
        st.title("📁 Chats")
        
        # --- NEW CHAT BUTTON ---
        if st.button("➕ New Chat", use_container_width=True):
            _handle_new_chat()
            st.session_state.title = "new chat"

        st.divider()

        # --- SYNC HISTORY ---
        if token and not st.session_state.get("history_synced"):
            _sync_history(token)

        sessions = (
            st.session_state.get("sessions", []) 
            if st.session_state.get("user_status") == "registered" 
            else st.session_state.get("guest_sessions", [])
        )

        if not sessions:
            st.caption("No previous chats")
        else:
            with st.container(height=250, border=False):
                current_active = st.session_state.get("active_session_id")
                for s in sessions:
                    sid = s.get("session_id") if isinstance(s, dict) else s
                    title = (s.get("title") if isinstance(s, dict) else None) or f"Chat {sid[:8]}"
                    is_active = (sid == current_active)
                    if is_active:
                        st.session_state.title = title
                    
                    if st.button(
                        f"{'🟢🟢' if is_active else ''} {title} {'🟢🟢' if is_active else ''}", 
                        key=f"side_{sid}", 
                        use_container_width=True
                    ):
                        switch_session(sid)

        # --- AUTH SECTION (Docks to bottom) ---
        # This divider stays below the scrollable container
        st.divider()
        
        if token and user:
            with st.container(border=True):
                st.markdown(f"👤 **{user.get('name', 'User')}**")
                st.caption(user.get('email', ''))
                if st.button("🚪 Logout", use_container_width=True):
                    _handle_logout()
        else:
            render_login()

def _sync_history(token):
    """Fetch history from backend for registered users."""
    try:
        data = load_home(token)
        st.session_state.sessions = data.get("sessions", [])
        st.session_state.user_status = "registered"
        st.session_state.history_synced = True 
        st.rerun()
    except Exception as e:
        st.session_state.history_synced = True 
        st.sidebar.error("Note: Cloud history unavailable.")

def _handle_new_chat():
    """Sets up a fresh session without adding it to the list yet."""
    new_id = str(uuid.uuid4())
    
    # We update the session IDs but DON'T push to the 'sessions' list
    # The promotion logic in render_chat_window will handle that after 1st message
    st.session_state.session_id = new_id
    st.session_state.active_session_id = new_id 
    st.session_state.messages = []
    st.session_state.uploaded_pdfs = []
    st.session_state.urls = []
    st.session_state.processing = False
    st.rerun()

def _handle_logout():
    """Wipes session and generates a fresh guest ID."""
    keys_to_clear = [
        "access_token", "user", "sessions", "history_synced", 
        "messages", "active_session_id", "uploaded_pdfs", "urls",
        "guest_sessions" # Clear guest chats on logout too if desired
    ]
    for key in keys_to_clear:
        st.session_state.pop(key, None)
    
    st.session_state.user_status = "guest"
    # Essential: generate a brand new UUID for the fresh guest state
    st.session_state.session_id = str(uuid.uuid4())
    st.rerun()