import streamlit as st
import httpx
from utils.config import BACKEND_URL

def render_login():
    """Renders a login button pointing to FastAPI."""
    login_url = f"{BACKEND_URL}/login/google"
    st.sidebar.link_button("🚀 Sign in with Google", login_url, use_container_width=True)

def check_auth_callback():
    """Exchanges Google code for JWT and claims guest sessions."""
    query_params = st.query_params
    if "code" in query_params and "access_token" not in st.session_state:
        auth_code = query_params["code"]
        
        try:
            with httpx.Client() as client:
                # 1. Get Token
                response = client.get(f"{BACKEND_URL}/auth/callback", params={"code": auth_code})
                response.raise_for_status()
                auth_data = response.json()

                # 2. Update Session State
                st.session_state.access_token = auth_data["access_token"]
                st.session_state.user = auth_data["user"]
                st.session_state.user_status = "registered"

                # 3. Claim Guest Sessions if one exists
                if "session_id" in st.session_state:
                    client.post(
                        f"{BACKEND_URL}/auth/claim_sessions",
                        json={"session_ids": [st.session_state.session_id]},
                        headers={"Authorization": f"Bearer {auth_data['access_token']}"}
                    )
            
            st.query_params.clear()
            st.toast(f"Welcome, {auth_data['user']['name']}!")
            st.rerun()
        except Exception as e:
            st.error(f"Auth failed: {e}")