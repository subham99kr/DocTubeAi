from api.home_client import load_home
import streamlit as st


def load_all_chats():
    token = st.session_state.get("access_token")
    if token:
        data = load_home(token)
        st.session_state.past_chats = data.get("sessions",[])
        
        
