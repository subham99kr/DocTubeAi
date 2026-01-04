import uuid
import logging
from fastapi import APIRouter, Depends
from typing import List, Dict, Optional
from pydantic import BaseModel
from global_modules.pg_pool import get_pg_pool
from auth.dependencies import get_current_user_optional

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Home"])

class SessionBrief(BaseModel):
    session_id: str
    title: Optional[str] = "New Chat"
    pdfs_uploaded: List[str]
    url_links: List[Dict[str, str]]
    updated_at: str

class HomeDataResponse(BaseModel):
    new_session_id: str
    history: List[SessionBrief]
    user_status: str

@router.get("/home_init", response_model=HomeDataResponse)
async def initialize_home_data(
    oauth_id: Optional[str] = Depends(get_current_user_optional)
):
    """
    Input Params = Oauth_id from header.
    Get all the sessions and list of {pdfs + urls} for each session.

    note: sends a new session id for new chat.
    """
    new_id = str(uuid.uuid4())
    
    if not oauth_id:
        return {
            "new_session_id": new_id,
            "history": [],
            "user_status": "guest"
        }

    pool = await get_pg_pool()
    
    query = """
        SELECT session_id, title, pdfs_uploaded, url_links, last_activity
        FROM sessions 
        WHERE oauth_id = %s 
        ORDER BY last_activity DESC;
    """
    
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, (oauth_id,))
            rows = await cur.fetchall()
            
            history = []
            for row in rows:
                history.append({
                    "session_id": row[0],
                    "title": row[1] or "New Chat",
                    "pdfs_uploaded": row[2] if row[2] is not None else [],
                    "url_links": row[3] if row[3] is not None else [],
                    "updated_at": row[4].isoformat() if row[4] else ""
                })
            
            return {
                "new_session_id": new_id,
                "history": history,
                "user_status": "registered"
            }