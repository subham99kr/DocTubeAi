import requests
import streamlit as st
from utils.config import BACKEND_URL

def upload_pdfs_api(files, session_id, token=None):
    url = f"{BACKEND_URL}/uploads/pdfs"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    # 1. Match the backend parameter name: 'files'
    # We use a list of tuples for List[UploadFile]
    multi_files = [
        ("files", (f.name, f.getvalue(), "application/pdf")) 
        for f in files
        if f is not None and f.size > 0 and f.name.strip() != ""
    ]
    if not multi_files:
        st.error("No valid PDF files to upload")
        return None

    
    # 2. session_id must be in 'data' to be a Form field
    form_data = {"session_id": session_id}
    if not session_id:
        st.error("Session ID missing")
        return None


    try:
        # Do NOT add 'Content-Type': 'multipart/form-data' to headers manually
        # requests does it better automatically when you pass 'files='
        response = requests.post(url, headers=headers, files=multi_files, data=form_data)
        
        if response.status_code == 422:
            st.error(f"Backend Validation Error: {response.json().get('detail')}")
            return None
            
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"PDF Upload Error: {e}")
        return None

def load_transcript_api(youtube_url, session_id, token=None):
    url = f"{BACKEND_URL}/transcripts/load"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    # Matches Pydantic model: TranscriptRequest
    payload = {
        "url": youtube_url,
        "session_id": session_id
    }

    try:
        # json= automatically sets 'application/json'
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 422:
            st.error(f"Transcript Validation Error: {response.json().get('detail')}")
            return None
            
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Transcript Error: {e}")
        return None