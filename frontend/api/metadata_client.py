import requests
from utils.config import BACKEND_URL

def load_metadata(session_id, token=None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    res = requests.get(
        f"{BACKEND_URL}/load_session_files_urls",
        params={"session_id": session_id},
        headers=headers,
    )
    res.raise_for_status()
    return res.json()
