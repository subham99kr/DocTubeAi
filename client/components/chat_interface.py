import streamlit as st

def render_chat_window():
    """Renders the message history container."""

    st.markdown("""
    <style>
    .chat-container {
        height: 65vh;        
        overflow-y: auto;
        border-radius: 8px;
        padding: 10px;
    }
    </style>
    """, unsafe_allow_html=True)

    chat_container = st.container()

    with chat_container:
        st.markdown('<div class="chat-container">', unsafe_allow_html=True)

        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

        st.markdown('</div>', unsafe_allow_html=True)

    return chat_container
