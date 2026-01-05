import requests
from utils.config import BACKEND_URL

def load_home(token: str | None = None):
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    r = requests.get(
        f"{BACKEND_URL}/home_init",
        headers=headers,
        timeout=10
    )
    r.raise_for_status()
    return r.json()
