import streamlit as st

def render_chat_input():
    """Renders the chat input bar and handles the initial locking stage."""
    # disabled=st.session_state.processing instantly dims the bar when thinking
    if prompt := st.chat_input(
        "Ask a question about your documents...", 
        # disabled=st.session_state.get("processing", False)
    ):
        # STAGE 1: Lock the UI and store the prompt for processing
        st.session_state.processing = True
        st.session_state.current_prompt = prompt
        st.rerun()