import requests, json
from utils.config import BACKEND_URL
import streamlit as st

def stream_chat(query):
    payload = {
        "query": query,
        "session_id": st.session_state.session_id,
    }

    with requests.post(
        f"{BACKEND_URL}/ask/stream",
        json=payload,
        stream=True,
        timeout=120,
    ) as r:
        for line in r.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            yield json.loads(line.replace("data:", "").strip())
