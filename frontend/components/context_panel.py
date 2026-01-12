import streamlit as st

def render_context():
    with st.expander("📎 Session Context", expanded=False):
        # 1. PDFs Section
        if "pdfs" in st.session_state and st.session_state.pdfs:
            st.markdown("**PDFs Uploaded**")
            for p in st.session_state.pdfs:
                st.write(f"📄 {p}")

        # 2. URLs Section (Showing Titles)
        if "urls" in st.session_state and st.session_state.urls:
            st.markdown("**Links Used**")
            for u in st.session_state.urls:
                # Logic: Use title if exists, otherwise fallback to URL
                display_text = u.get('title') or u.get('url', 'Unknown Link')
                st.write(f"🔗 {display_text}")