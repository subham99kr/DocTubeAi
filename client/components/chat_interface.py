import streamlit as st

def render_chat_window():
    """Renders the message history bubbles only."""
    chat_container = st.container(height=490)

    with chat_container:
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    return chat_container