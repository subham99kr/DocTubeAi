import streamlit as st
from state.session_state import initialize_session
from components.sidebar import render_sidebar
from components.chat_interface import render_chat_window
from components.status_bar import render_status
from api.auth_client import check_auth_callback

st.set_page_config(page_title="RAG Assistant", page_icon="🤖", layout="wide")

# 1. Catch the code and clear it from the URL immediately
check_auth_callback()

# 2. Initialize the rest of the app
initialize_session()
render_sidebar()
st.title(st.session_state.get("title"))
render_status()
render_chat_window()