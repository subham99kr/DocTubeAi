from global_modules.pg_pool import get_pg_pool
from fastapi import HTTPException
from typing import Optional

async def verify_and_initialize_session(session_id: str, oauth_id: Optional[str] = None):
    """
    1. If session doesn't exist: Create it (assign oauth_id if provided).
    2. If session exists: Check if current user has permission to use it.
    """
    pool = await get_pg_pool()
    
    # This query attempts to create the session if it's missing.
    # If it already exists, it does nothing ('DO NOTHING').
    upsert_query = """
        INSERT INTO sessions (session_id, oauth_id)
        VALUES (%s, %s)
        ON CONFLICT (session_id) DO NOTHING;
    """
    
    # This query checks who owns the session.
    check_query = "SELECT oauth_id FROM sessions WHERE session_id = %s"

    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            # Step 1: Ensure the session exists in DB
            await cur.execute(upsert_query, (session_id, oauth_id))
            
            # Step 2: Fetch the actual owner from DB
            await cur.execute(check_query, (session_id,))
            result = await cur.fetchone()
            
            db_oauth_id = result[0]

            # Step 3: Privacy Check
            # If the session is owned (not NULL), but the current user doesn't match
            if db_oauth_id is not None and db_oauth_id != oauth_id:
                raise HTTPException(
                    status_code=403, 
                    detail="This session belongs to another user. Please log in with the correct account."
                )
            
            return True