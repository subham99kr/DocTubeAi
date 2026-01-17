import logging
from fastapi import APIRouter, Depends
from typing import List, Optional
from pydantic import BaseModel
from global_modules.pg_pool import get_pg_pool
from auth.dependencies import get_current_user_optional

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Home"])

class SessionBrief(BaseModel):
    session_id: str
    title: Optional[str] = "New Chat"
    updated_at: str

class HomeDataResponse(BaseModel):
    sessions: List[SessionBrief] = []
    user_status: str = []

@router.get("/home_init", response_model=HomeDataResponse)
async def initialize_home_data(
    oauth_id: Optional[str] = Depends(get_current_user_optional)
):
    """
    Input Params = Oauth_id from header.
    Get all the sessions and list of {pdfs + urls} for each session.

    note: sends a new session id for new chat.
    """
    
    if not oauth_id:
        return {
            "sessions": [],
            "user_status": "guest"
        }

    pool = await get_pg_pool()
    
    query = """
        SELECT session_id, title,last_activity
        FROM sessions 
        WHERE oauth_id = %s 
        ORDER BY last_activity DESC limit 20;
    """
    
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, (oauth_id,))
            rows = await cur.fetchall()
            
            sessions = []
            for row in rows:
                sessions.append({
                    "session_id": row[0],
                    "title": row[1] or "New Chat",
                    "updated_at": row[2].isoformat() if row[2] else ""
                })
            
            return {
                "sessions": sessions,
                "user_status": "registered"
            }