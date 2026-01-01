import logging
from fastapi import APIRouter, HTTPException, Depends # Added Depends
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from global_modules.pg_pool import get_pg_pool
from auth.dependencies import get_current_user_optional # Our Guard

logger = logging.getLogger(__name__)
router = APIRouter()

class SessionMetadataResponse(BaseModel):
    session_id: str
    pdfs_uploaded: List[str]
    url_links: List[Dict[str, str]]

@router.get("/load_session_files_urls", response_model=SessionMetadataResponse)
async def get_session_metadata(
    session_id: str, 
    # Use the dependency to get the verified ID from the JWT
    oauth_id: Optional[str] = Depends(get_current_user_optional)
):
    """
    Fetches both PDF filenames and YouTube URL links for a given session.
    Only allows access if the oauth_id matches or the session is public.
    """
    # 1. Verification Logic
    # We fetch the metadata ONLY if the oauth matches.
    data = await get_session_metadata_internal(session_id, oauth_id)
    
    # 2. If the internal function found nothing or denied access
    if not data:
        raise HTTPException(
            status_code=403, 
            detail="Unauthorized or Session not found."
        )

    return {
        "session_id": session_id,
        "pdfs_uploaded": data["pdfs_uploaded"],
        "url_links": data["url_links"]
    }

async def get_session_metadata_internal(session_id: str, oauth_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """
    Fetches metadata with an ownership check.
    """
    pool = await get_pg_pool()
    
    # Ownership Check: 
    # Match the session_id AND (oauth is either NULL or matches the current user)
    query = """
        SELECT pdfs_uploaded, url_links 
        FROM sessions 
        WHERE session_id = %s 
        AND (oauth_id = %s OR oauth_id IS NULL);
    """
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (session_id, oauth_id))
                result = await cur.fetchone()
                
                if result:
                    return {
                        "pdfs_uploaded": list(result[0]) if result[0] else [],
                        "url_links": result[1] if result[1] else []
                    }
                return None # No access or doesn't exist
                
    except Exception as e:
        logger.error(f"🔴 DB Error fetching metadata for {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Database retrieval error")