import requests
import streamlit as st
from utils.config import BACKEND_URL

def upload_pdfs_api(files, session_id, token=None):
    if not session_id:
        st.error("Session ID missing")
        return None
    
    url = f"{BACKEND_URL}/uploads/pdfs"
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    
    multi_files = [
        ("files", (f.name, f.getvalue(), "application/pdf"))
        for f in files
        if f and f.name.strip() and len(f.getvalue()) > 0
    ]

    if not multi_files:
        st.error("No valid PDF files to upload")
        return None

    
    try:
        response = requests.post(
            url,
            headers=headers,
            files=multi_files,
            data={"session_id": session_id},
            timeout=60
        )

        if response.status_code == 422:
            detail = (
                response.json().get("detail")
                if response.headers.get("content-type", "").startswith("application/json")
                else response.text
            )
            st.error(f"Backend Validation Error: {detail}")
            return None

        response.raise_for_status()
        return response.json()

    except requests.exceptions.Timeout:
        st.error("Upload timed out. Please try again.")
        return None
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