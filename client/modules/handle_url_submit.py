import streamlit as st

def handle_url_submit(url):
    """Submits a URL and appends the metadata object to local state."""
    from api.upload_client import load_transcript_api
    
    st.session_state.processing = True
    # API returns metadata: {"url": "...", "title": "...", "added_at": "..."}
    new_link_data = load_transcript_api(url, st.session_state.active_session_id, st.session_state.access_token)
    
    
    if new_link_data:
        # Append the new link object directly
        title = new_link_data.get('title', '')
        st.session_state.urls.append(title)
        st.toast(f"🔗 Added: {new_link_data.get('title', 'New Link')}")
        
    st.session_state.processing = False
    st.rerun()