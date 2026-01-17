import streamlit as st

def render_status():
    if st.session_state.status:
        st.info(st.session_state.status)
