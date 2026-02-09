import streamlit as st

def render_chat_window():
    """Renders a scrollable chat window with aligned messages and rounded bubbles."""

    # 1. CSS to fix the window height and style the internal chat bubbles
    st.markdown("""
    <style>
    /* Fix the overall chat area height */
    .chat-wrapper {
        height: 0vh; 
        overflow-y: auto;
        padding: 0rem;
        display: flex;
        flex-direction: column;
    }

    /* Target the ACTUAL chat bubbles to show border radius */
    [data-testid="stChatMessage"] {
        border-radius: 1.5rem !important; /* This creates the rounded look */
        padding: 0.5rem 1rem !important;
        margin-bottom: 1rem !important;
        border: 1px solid #30363d !important; /* Makes the edge visible */
    }

    /* Optional: Slightly different background for the bubbles */
    [data-testid="stChatMessageContent"] {
        font-size: 0.95rem;
    }
    </style>
    """, unsafe_allow_html=True)

    # 2. Use a main container
    main_container = st.container()

    with main_container:
        # Wrap everything in our scrollable div
        st.markdown('<div class="chat-wrapper">', unsafe_allow_html=True)

        for msg in st.session_state.messages:
            if msg["role"] == "user":
                # USER -> ALIGN RIGHT
                # We use columns to push the message to the right
                col1, col2 = st.columns([1, 3]) 
                with col2:
                    with st.chat_message("user"):
                        st.markdown(msg["content"])
            else:
                # AI -> ALIGN LEFT
                col1, col2 = st.columns([3, 1])
                with col1:
                    with st.chat_message("assistant"):
                        st.markdown(msg["content"])

        st.markdown('</div>', unsafe_allow_html=True)

    return main_container
