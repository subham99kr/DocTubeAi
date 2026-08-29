import streamlit as st
from api.home_client import load_home


def load_all_chats():
    token = st.session_state.get("access_token")
    if token:
        data = load_home(token)
        st.session_state.past_chats = data.get("sessions",[])
        
        
