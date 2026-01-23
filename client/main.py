import streamlit as st
from state.session_state import initialize_session
from components.sidebar import render_sidebar
from components.chat_interface import render_chat_window
from api.auth_client import check_auth_callback
from components.chat_input import render_chat_input
from components.context_panel import render_context_bar
from modules.chat_handler import handle_chat_logic

st.set_page_config(page_title="DocTubeAi", page_icon="📗", layout="wide")



# bootstrap_auth()
check_auth_callback()

initialize_session()

render_sidebar()

# col1, col2 = st.columns([5, 1], gap="small")

# with col1:
title = st.session_state.get("title", "New Chat")

st.markdown(f"""
<style>

header[data-testid="stHeader"] {{
    display: none;
}}

div.block-container {{
    padding-top: 70px !important;
}}

.app-header {{
    position: fixed;
    top: 0;
    height: 8%;
    width: 100%;
    background: #0e1117;
    color: white;
    display: flex;
    align-items: center;
    padding: 0 20px;
    font-size: 20px;
    font-weight: 600;
    border-bottom: 1px solid #2c2f33;
    z-index: 99999;
    transition: all 0.2s ease;
}}

</style>

<div id="app-header" class="app-header">
📗 DocTubeAI — {title}
</div>

<script>
function updateHeader() {{
    const sidebar = document.querySelector('[data-testid="stSidebar"]');
    const header = document.getElementById("app-header");

    if (!sidebar || !header) return;

    const sidebarWidth = sidebar.offsetWidth;
    header.style.left = sidebarWidth + "px";
    
}}

updateHeader();

const observer = new ResizeObserver(updateHeader);
const sidebar = document.querySelector('[data-testid="stSidebar"]');
if (sidebar) observer.observe(sidebar);
</script>
""", unsafe_allow_html=True)





# render_status()

chat_box = render_chat_window()

handle_chat_logic(chat_box)

# with col2:
render_context_bar()

render_chat_input()