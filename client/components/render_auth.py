import streamlit as st
import requests
from utils.config import BACKEND_URL


def check_auth_callback():
    # Only proceed if there is a code in the URL and NO token in state
    params = st.query_params
    if "code" in params and not st.session_state.get("access_token"):
        code = params["code"]
        try:
            # Exchange the code for a token
            response = requests.get(f"{BACKEND_URL}/auth/callback", params={"code": code})
            response.raise_for_status()
            data = response.json()

            # Save data to state
            st.session_state.access_token = data.get("access_token")
            st.session_state.user = data.get("user")
            st.session_state.user_status = "registered"
            
            # SUCCESS: Now clear the URL so this code isn't used again
            st.query_params.clear()
            st.rerun()

        except Exception as e:
            # If it fails, clear the URL anyway to stop the infinite 400 error loop
            st.query_params.clear()
            st.error(f"Authentication failed or code expired. Please log in again.")