from fastapi import APIRouter, Depends, HTTPException
from typing import List
from pydantic import BaseModel
from global_modules.pg_pool import get_pg_pool
from auth.dependencies import get_current_user_optional

router = APIRouter(tags=["Auth Cleanup"])

class ClaimSessionsRequest(BaseModel):
    session_ids: List[str]   #make sure you don't send the new chat session without any message

@router.post("/auth/claim_sessions")
async def claim_guest_sessions(
    req: ClaimSessionsRequest,
    oauth_id: str = Depends(get_current_user_optional) 
):
    """
    Takes a list of local session IDs and attaches them to the 
    permanent user profile if they don't already have an owner.
    """
    if not oauth_id:
        raise HTTPException(status_code=401, detail="Authentication required to claim sessions.")

    if not req.session_ids:
        return {"status": "success", "claimed_count": 0}

    pool = await get_pg_pool()
    
    # SQL logic: Update the oauth_id ONLY if it is currently NULL
    # This prevents users from "stealing" someone else's session by guessing IDs.
    query = """
        UPDATE sessions 
        SET oauth_id = %s 
        WHERE session_id = ANY(%s) 
        AND oauth_id IS NULL;
    """
    
    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(query, (oauth_id, req.session_ids))
                updated_count = cur.rowcount # Tells us how many rows were updated
            await conn.commit()
            
            return {
                "status": "success", 
                "claimed_count": updated_count,
                "message": f"Successfully linked {updated_count} guest sessions to your account."
            }

    except Exception as e:
        import logging
        logging.error(f"🔴 Session Claiming failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to link guest sessions.")