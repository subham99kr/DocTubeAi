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
        
        if st.button("➕ New Chat", use_container_width=True):
            _handle_new_chat()

        st.divider()

        # --- SYNC HISTORY ---
        if token and not st.session_state.get("history_synced"):
            _sync_history(token)

        # --- CHAT LIST ---
        sessions = (
            st.session_state.get("sessions", []) 
            if st.session_state.get("user_status") == "registered" 
            else st.session_state.get("guest_sessions", [])
        )

        if not sessions:
            st.caption("No previous chats")
        else:
            current_active = st.session_state.get("active_session_id")
            for s in sessions:
                sid = s.get("session_id") if isinstance(s, dict) else s
                title = (s.get("title") if isinstance(s, dict) else None) or f"Chat {sid[:8]}"
                is_active = (sid == current_active)
                
                if st.button(f"{'▶️' if is_active else '💬'} {title}", key=f"side_{sid}", use_container_width=True):
                    switch_session(sid)

        # --- AUTH SECTION (Docks to bottom) ---
        for _ in range(8): st.write("") 
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
    try:
        from api.home_client import load_home
        data = load_home(token)
        st.session_state.sessions = data.get("sessions", [])
        st.session_state.user_status = "registered"
        st.session_state.history_synced = True 
        st.rerun()
    except Exception as e:
        st.session_state.history_synced = True 
        st.sidebar.error("Note: Cloud history unavailable.")

def _handle_new_chat():
    new_id = str(uuid.uuid4())
    new_chat = {"session_id": new_id, "title": "New Chat ✨"}
    
    # # Add to the correct list based on status
    # if st.session_state.get("user_status") == "registered":
    #     if "sessions" not in st.session_state: st.session_state.sessions = []
    #     st.session_state.sessions.insert(0, new_chat)
    # else:
    #     if "guest_sessions" not in st.session_state: st.session_state.guest_sessions = []
    #     st.session_state.guest_sessions.insert(0, new_chat)
    
    # Update active state
    st.session_state.session_id = new_id
    st.session_state.active_session_id = new_id 
    st.session_state.messages = []
    st.session_state.uploaded_pdfs = []
    st.session_state.urls = []
    st.session_state.processing = False
    st.rerun()

def _handle_logout():
    # 1. Clear all user-specific data
    keys_to_clear = [
        "access_token", "user", "sessions", "history_synced", 
        "messages", "active_session_id", "uploaded_pdfs", "urls"
    ]
    for key in keys_to_clear:
        st.session_state.pop(key, None)
    
    # 2. Reset to Guest status
    st.session_state.user_status = "guest"
    
    # 3. CRITICAL: Generate a fresh UUID for the new Guest session
    # This prevents sending an empty or old session_id to the backend
    st.session_state.session_id = str(uuid.uuid4())
    
    st.rerun()