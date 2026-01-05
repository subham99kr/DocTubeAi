import requests
from utils.config import BACKEND_URL

def load_history(session_id, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    res = requests.get(f"{BACKEND_URL}/chats/history/{session_id}", headers=headers)
    res.raise_for_status()
    return res.json()["history"]
