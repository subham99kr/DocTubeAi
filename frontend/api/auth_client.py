import streamlit as st
import httpx
from utils.config import BACKEND_URL


def render_login():
    """Renders a polished Google Sign-in button for the sidebar."""
    login_url = f"{BACKEND_URL}/login/google"
    
    # Using official Google colors and a clean shadow effect
    login_button_html = f"""
        <style>
            .login-btn {{
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 10px;
                background-color: #ffffff;
                color: #3c4043 !important;
                padding: 10px 16px;
                border-radius: 8px;
                text-decoration: none;
                font-family: 'Roboto', sans-serif;
                font-size: 14px;
                font-weight: 500;
                width: 100%;
                border: 1px solid #dadce0;
                transition: background-color 0.2s, box-shadow 0.2s;
                box-sizing: border-box;
                box-shadow: 0 1px 2px 0 rgba(60,64,67,0.3), 0 1px 3px 1px rgba(60,64,67,0.15);
            }}
            .login-btn:hover {{
                background-color: #f8f9fa;
                box-shadow: 0 1px 2px 0 rgba(60,64,67,0.3), 0 2px 6px 2px rgba(60,64,67,0.15);
                border-color: #d2d4d7;
            }}
            .google-icon {{
                width: 18px;
                height: 18px;
            }}
        </style>
        <a href="{login_url}" target="_top" class="login-btn">
            <img class="google-icon" src="https://fonts.gstatic.com/s/i/productlogos/googleg/v6/24px.svg" alt="Google logo">
            Sign in with Google
        </a>
    """
    st.sidebar.markdown(login_button_html, unsafe_allow_html=True)

def check_auth_callback():
    """Exchanges Google code for JWT and claims guest sessions."""
    query_params = st.query_params
    
    if "code" in query_params and "access_token" not in st.session_state:
        auth_code = query_params["code"]
        
        try:
            with httpx.Client() as client:
                # 1. Exchange Auth Code for JWT
                response = client.get(
                    f"{BACKEND_URL}/auth/callback", 
                    params={"code": auth_code},
                    timeout=10.0
                )
                response.raise_for_status()
                auth_data = response.json()

                # 2. Update Session State
                st.session_state.access_token = auth_data["access_token"]
                st.session_state.user = auth_data["user"]
                st.session_state.user_status = "registered"
                st.session_state.history_synced = False

                # 3. Claim Guest Sessions
                guest_sessions = st.session_state.get("guest_sessions", [])
                session_ids_to_claim = [s["session_id"] for s in guest_sessions]
                
                current_sid = st.session_state.get("session_id")
                if current_sid and current_sid not in session_ids_to_claim:
                    session_ids_to_claim.append(current_sid)

                if session_ids_to_claim:
                    client.post(
                        f"{BACKEND_URL}/auth/claim_sessions",
                        json={"session_ids": session_ids_to_claim},
                        headers={"Authorization": f"Bearer {auth_data['access_token']}"}
                    )
            
            # 4. Cleanup
            st.query_params.clear()
            st.toast(f"Welcome back, {auth_data['user']['name']}!")
            st.rerun()
            
        except Exception as e:
            st.error(f"Authentication failed: {e}")
            st.query_params.clear()