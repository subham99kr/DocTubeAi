import streamlit as st
from api.stream_client import stream_rag_response

def render_chat_window():
    """
    Renders the message history and the fixed bottom input with instant dimming.
    """
    
    # 1. Display Message History
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 2. Render Fixed Bottom Input
    # disabled=True instantly dims and locks the bar
    if prompt := st.chat_input(
        "Ask a question about your documents...", 
        disabled=st.session_state.processing
    ):
        # STAGE 1: Lock the UI and store the prompt
        st.session_state.processing = True
        st.session_state.current_prompt = prompt
        st.rerun()  # Forces immediate redraw to show dimmed input

    # 3. Processing Phase (Runs after the rerun triggered above)
    if st.session_state.processing and "current_prompt" in st.session_state:
        prompt_to_process = st.session_state.pop("current_prompt")
        _handle_chat_logic(prompt_to_process)

def _handle_chat_logic(prompt):
    """Internal logic to handle streaming, sidebar promotion, and unlocking UI."""
    
    # 1. Determine if this is the first message
    # We check the list length before adding the new prompt
    is_first_message = len(st.session_state.messages) == 0
    sid = st.session_state.get("session_id")
    token = st.session_state.get("access_token")

    # 2. Sidebar Promotion (Immediate list update)
    if is_first_message:
        _promote_session_to_sidebar(prompt)

    # 3. Add user message to state and display
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 4. Assistant Response Streaming
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        
        try:
            # Stream the generator
            for chunk in stream_rag_response(sid, prompt, token):
                full_response += chunk
                response_placeholder.markdown(full_response + "▌")
            
            response_placeholder.markdown(full_response)
            
            # Save response to history
            st.session_state.messages.append({"role": "assistant", "content": full_response})

        except Exception as e:
            st.error(f"Chat Error: {e}")
        
        finally:
            # 5. UNLOCK UI & SYNC
            st.session_state.processing = False
            # Ensure the sidebar highlight matches this session
            st.session_state.active_session_id = sid
            
            # Final rerun to enable the input bar and refresh sidebar UI
            st.rerun()

def _promote_session_to_sidebar(first_query):
    """Creates a sidebar entry using the first 50 characters of the query."""
    current_sid = st.session_state.get("session_id")
    if not current_sid:
        return

    # Create the title from prompt
    new_title = first_query[:50] + ("..." if len(first_query) > 50 else "")
    new_entry = {
        "session_id": current_sid, 
        "title": new_title
    }

    # Determine correct session list
    user_status = st.session_state.get("user_status", "guest")
    list_key = "sessions" if user_status == "registered" else "guest_sessions"

    if list_key not in st.session_state:
        st.session_state[list_key] = []

    # Check for duplicates before inserting
    exists = any(s.get("session_id") == current_sid for s in st.session_state[list_key])
    
    if not exists:
        st.session_state[list_key].insert(0, new_entry)
        st.session_state.active_session_id = current_sid