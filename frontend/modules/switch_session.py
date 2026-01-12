import streamlit as st
from api.history_client import load_history

def switch_session(new_session_id):
    if new_session_id == st.session_state.get("active_session_id"):
        return
    
    token = st.session_state.get("access_token")
    data = load_history(new_session_id, token) 

    if data:
        # LOGGING: Helps you see if 'history' is actually there
        # st.write(f"DEBUG: Found {len(data.get('history', []))} messages")

        st.session_state.session_id = data.get("session_id")
        st.session_state.active_session_id = data.get("session_id")

        # Crucial: Use the exact key the backend sends
        # If your API uses "messages", change "history" to "messages" here
        st.session_state.messages = data.get("history", [])
        
        st.session_state.uploaded_pdfs = data.get("pdfs", [])

        # URL processing
        url_data = data.get("urls", [])
        st.session_state.urls = [
            u.get("title", "Untitled Link") for u in url_data 
            if isinstance(u, dict)
        ]
        
        st.session_state.processing = False
        st.rerun()
    else:
        st.error(f"Could not retrieve session data for {new_session_id}")