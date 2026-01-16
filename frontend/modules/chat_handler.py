import streamlit as st
from api.stream_client import stream_rag_response

def handle_chat_logic(chat_container): # <--- Receive the container here
    if not st.session_state.get("processing") or "current_prompt" not in st.session_state:
        return

    prompt = st.session_state.pop("current_prompt")
    sid = st.session_state.get("session_id")
    token = st.session_state.get("access_token")

    if len(st.session_state.messages) == 0:
        _promote_session_to_sidebar(prompt, sid)

    # Use the container to ensure messages appear INSIDE the scroll box
    with chat_container:
        # 1. Show User Message
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 2. Show Assistant Response
        with st.chat_message("assistant"):
            response_placeholder = st.empty()
            status_placeholder = st.empty()
            full_response = ""
            
            try:
                for event in stream_rag_response(sid, prompt, token):
                    if isinstance(event, dict) and event.get("type") == "status":
                        status_placeholder.markdown(f"✨ *{event['data']}*")
                    else:
                        status_placeholder.empty()
                        full_response += event
                        response_placeholder.markdown(full_response)
                
                st.session_state.messages.append({"role": "assistant", "content": full_response})

            except Exception as e:
                st.error(f"Chat Error: {e}")
            finally:
                st.session_state.processing = False
                st.rerun()

def _promote_session_to_sidebar(first_query, current_sid):
    """Internal helper to create a sidebar entry."""
    if not current_sid: return
    
    new_title = first_query[:50] + ("..." if len(first_query) > 50 else "")
    user_status = st.session_state.get("user_status", "guest")
    list_key = "sessions" if user_status == "registered" else "guest_sessions"
    
    if list_key not in st.session_state: st.session_state[list_key] = []
    
    if not any(s.get("session_id") == current_sid for s in st.session_state[list_key]):
        st.session_state[list_key].insert(0, {"session_id": current_sid, "title": new_title})