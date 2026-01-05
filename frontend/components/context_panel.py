import streamlit as st

def render_context():
    with st.expander("📎 Session Context", expanded=False):
        if st.session_state.pdfs:
            st.markdown("**PDFs Uploaded**")
            for p in st.session_state.pdfs:
                st.write(f"📄 {p}")

        if st.session_state.urls:
            st.markdown("**Links Used**")
            for u in st.session_state.urls:
                st.write(f"🔗 {u.get('url', '')}")
