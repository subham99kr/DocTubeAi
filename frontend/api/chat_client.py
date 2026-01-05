import requests
from utils.config import BACKEND_URL

def ask_chat(query, session_id, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    payload = {
        "query": query,
        "session_id": session_id
    }

    r = requests.post(
        f"{BACKEND_URL}/ask",
        json=payload,
        headers=headers,
        timeout=120
    )
    r.raise_for_status()
    return r.json()
