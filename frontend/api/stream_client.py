import json
import requests
import streamlit as st
from utils.config import BACKEND_URL

def stream_rag_response(session_id, query, token=None):
    url = f"{BACKEND_URL}/chats/ask/stream"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    payload = {"session_id": session_id, "query": query}

    # 1. Open the connection with stream=True
    response = requests.post(url, json=payload, headers=headers, stream=True)
    response.raise_for_status()

    status_placeholder = st.empty()
    last_status = None

    # 2. Iterate over the chunks
    for line in response.iter_lines():
        if not line:
            continue
        
        # DECODE AND CLEAN THE SSE PREFIX
        decoded_line = line.decode("utf-8")
        
        # SSE format sends lines starting with "data: "
        if decoded_line.startswith("data: "):
            # Remove the "data: " prefix (6 characters)
            json_str = decoded_line[6:].strip()
            
            try:
                # Now parse the actual JSON object
                chunk = json.loads(json_str)
                
                chunk_type = chunk.get("type")
                data = chunk.get("data", "")

                # CASE A: Status Updates 
                if chunk_type == "status":
                    if data != last_status:
                        status_placeholder.markdown(f" ✨✨ *{data}*")
                        last_status = data

                # CASE B: Actual Answer Tokens
                elif chunk_type == "token":
                    status_placeholder.empty() 
                    yield data
                
                # CASE C: Done
                elif chunk_type == "done":
                    status_placeholder.empty()
                    break

            except json.JSONDecodeError:
                # Skip lines that aren't valid JSON (like heartbeats if not formatted correctly)
                continue

    status_placeholder.empty()