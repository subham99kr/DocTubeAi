import streamlit as st
from state.session_state import initialize_session
from components.sidebar import render_sidebar
from components.chat_interface import render_chat_window
from components.status_bar import render_status
from api.auth_client import check_auth_callback
from components.chat_input import render_chat_input
from components.context_panel import render_top_bar
# from components.render_context import render_context
from modules.chat_handler import handle_chat_logic

# 1. Page Config
st.set_page_config(page_title="RAG Assistant", page_icon="🤖", layout="wide")

# 2. Auth & Session Initialization
check_auth_callback()
initialize_session()

# 3. Sidebar (Left)
render_sidebar()

# 4. Main Layout Columns
col1, col2 = st.columns([4, 1], gap="large")

with col1:
    # Header area
    st.title(st.session_state.get("title", "New Chat"))
    render_status()
    
    # Message History
    # with st.container(height=450):
    chat_box = render_chat_window()

    # THE MISSING PIECE: Execute the logic to handle the prompt if one exists
    handle_chat_logic(chat_box)

with col2:
    # Context Panel (Right side, vertical stack)
    render_top_bar()

render_chat_input()