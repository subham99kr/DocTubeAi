import requests
import streamlit as st
from utils.config import BACKEND_URL

def upload_pdfs_api(files, session_id, token=None):
    """Calls the /uploads/pdfs endpoint."""
    url = f"{BACKEND_URL}/uploads/pdfs"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    # Format files for multipart/form-data
    # files is a list of Streamlit UploadedFile objects
    multi_files = [("files", (f.name, f.getvalue(), f.type)) for f in files]
    data = {"session_id": session_id}

    try:
        response = requests.post(url, headers=headers, files=multi_files, data=data)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"PDF Upload Error: {e}")
        return None

def load_transcript_api(youtube_url, session_id, token=None):
    """Calls the /transcripts/load endpoint."""
    url = f"{BACKEND_URL}/transcripts/load"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    payload = {
        "url": youtube_url,
        "session_id": session_id
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Transcript Error: {e}")
        return None