import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from modules.verify_session import verify_and_initialize_session
from auth.dependencies import get_current_user_optional
from modules.load_transcript import load_transcript 

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/transcripts",
    tags=["Transcripts"]
)

class TranscriptRequest(BaseModel):
    url: str
    session_id: str

# --- Router Endpoint ---
@router.post("/load")
async def load_transcripts_endpoint(
    request_data: TranscriptRequest, 
    oauth_id: Optional[str] = Depends(get_current_user_optional)
):
    """
    JSON-based endpoint to load a YouTube transcript into a session.
    The database update is now handled internally by load_transcript.
    """
    session_id = request_data.session_id
    url = request_data.url

    # 1. Security & Lifecycle check (Updates last_activity)
    await verify_and_initialize_session(session_id, oauth_id)
    
    try:
        # 2. Extract, Ingest, and Update DB
        # This function now handles: extracting text -> splitting -> MongoDB -> Postgres update
        video_title = await load_transcript(url, session_id=session_id)

        return JSONResponse(
            status_code=200, 
            content={"status": "Success", "session_id": session_id, "title":video_title}
        )

    except HTTPException as he:
        # Pass through specific errors (404, 403, etc.) from the extractor
        raise he
    except Exception as e:
        logger.exception("Failed to load transcript")
        return JSONResponse(
            status_code=500, 
            content={"error": "An internal error occurred while processing the transcript"}
        )