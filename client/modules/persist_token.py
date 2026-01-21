import streamlit as st
import json

def store_token(token: str):
    st.session_state["access_token"] = token
    safe_token = json.dumps(token)
    st.markdown(f"""
    <script>
        localStorage.setItem("access_token", "{token}");
    </script>
    """, unsafe_allow_html=True)


def bootstrap_auth():
    # 1. Token already in session → done
    if st.session_state.get("access_token"):
        return

    # 2. Token coming from URL (JS bridge)
    params = st.query_params
    token = params.get("access_token")

    if token:
        st.session_state["access_token"] = token
        st.query_params.clear()
        st.rerun()

    # 3. Ask JS to read localStorage
    inject_localstorage_reader()
    # st.stop()


def inject_localstorage_reader():
    st.markdown("""
    <script>
        (function() {
            const token = localStorage.getItem("access_token");
            if (token && !window.location.search.includes("access_token")) {
                const url = new URL(window.location);
                url.searchParams.set("access_token", token);
                window.location.replace(url.toString());
            }
        })();
    </script>
    """, unsafe_allow_html=True)
