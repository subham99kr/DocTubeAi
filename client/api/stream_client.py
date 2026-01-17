import json
import requests
import streamlit as st
from utils.config import BACKEND_URL


def stream_rag_response(session_id, query, token=None):
    url = f"{BACKEND_URL}/chats/ask/stream"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    payload = {"session_id": session_id, "query": query}

    response = requests.post(
        url,
        json=payload,
        headers=headers,
        stream=True,
    )
    response.raise_for_status()

    last_status = None

    try:
        for line in response.iter_lines():
            if not line:
                continue

            decoded = line.decode("utf-8")
            if not decoded.startswith("data: "):
                continue

            try:
                chunk = json.loads(decoded[6:].strip())
            except json.JSONDecodeError:
                continue

            chunk_type = chunk.get("type")
            data = chunk.get("data", "")

            if chunk_type == "status":
                yield {"type": "status", "data": data}

            elif chunk_type == "token":
                yield data

            elif chunk_type == "done":
                break

    finally:
        try:
            response.close()
        except Exception:
            pass
