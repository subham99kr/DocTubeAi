# from fastapi import APIRouter, Depends, HTTPException
# from typing import List, Optional
# from pydantic import BaseModel
# from global_modules.pg_pool import get_pg_pool
# from auth.dependencies import get_current_user_optional

# router = APIRouter(tags=["Session History"])

# class UserSessionSchema(BaseModel):
#     session_id: str
#     pdfs_uploaded: List[str]
#     created_at: str # Or datetime

# @router.get("/user/sessions", response_model=List[UserSessionSchema])
# async def get_user_sessions(
#     oauth_id: Optional[str] = Depends(get_current_user_optional)
# ):
#     """
#     Retrieves all chat sessions belonging to the logged-in user.
#     """
#     if not oauth_id:
#         # If no JWT is provided, we can't look up a history.
#         # We return an empty list rather than an error for a better UI experience.
#         return []

#     pool = await get_pg_pool()
    
#     # We select sessions where the oauth_id matches the one decrypted from the JWT
#     query = """
#         SELECT session_id,title 
#         FROM sessions 
#         WHERE oauth_id = %s 
#         ORDER BY created_at DESC;
#     """
    
#     try:
#         async with pool.connection() as conn:
#             async with conn.cursor() as cur:
#                 await cur.execute(query, (oauth_id,))
#                 rows = await cur.fetchall()
                
#                 # Map the database rows to our list of dictionaries
#                 sessions = [
#                     {
#                         "session_id": row[0],
#                         "pdfs_uploaded": row[1] if row[1] else [],
#                         "created_at": row[2].isoformat() if row[2] else ""
#                     }
#                     for row in rows
#                 ]
#                 return sessions

#     except Exception as e:
#         import logging
#         logging.error(f"🔴 Failed to fetch user sessions: {e}")
#         raise HTTPException(status_code=500, detail="Could not retrieve session history.")