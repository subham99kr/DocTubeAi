import streamlit as st
from state.session_state import initialize_session
from components.sidebar import render_sidebar
from components.chat_interface import render_chat_window
from components.status_bar import render_status
from api.auth_client import check_auth_callback
from components.chat_input import render_chat_input
from components.context_panel import render_context_bar
from modules.chat_handler import handle_chat_logic
# from modules.persist_token import bootstrap_auth

st.set_page_config(page_title="DocTubeAi", page_icon="📗", layout="wide")



# bootstrap_auth()
check_auth_callback()

initialize_session()

render_sidebar()

col1, col2 = st.columns([5, 1], gap="small")

with col1:
    st.title(st.session_state.get("title", "New Chat"))
    render_status()
    
    chat_box = render_chat_window()

    handle_chat_logic(chat_box)

with col2:
    render_context_bar()

render_chat_input()