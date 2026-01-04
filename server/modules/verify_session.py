from global_modules.pg_pool import get_pg_pool
from fastapi import HTTPException
from typing import Optional
import logging

logger = logging.getLogger(__name__)

async def verify_and_initialize_session(session_id: str, oauth_id: Optional[str] = None):
    """
    1. Creates the session if it doesn't exist.
    2. Updates 'last_activity' to NOW() if it does exist.
    3. Verifies that the 'oauth_id' matches the session owner.
    """
    pool = await get_pg_pool()
    
    # 1. UPSERT: Insert new or update existing last_activity
    # We use RETURNING to get the existing oauth_id in the same call
    upsert_query = """
        INSERT INTO sessions (session_id, oauth_id, last_activity)
        VALUES (%s, %s, NOW())
        ON CONFLICT (session_id) 
        DO UPDATE SET last_activity = NOW()
        RETURNING oauth_id;
    """

    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # Execute the upsert and fetch the owner
                await cur.execute(upsert_query, (session_id, oauth_id))
                result = await cur.fetchone()
                
                if not result:
                    # This should theoretically not happen with an UPSERT
                    raise HTTPException(status_code=500, detail="Session initialization failed.")

                db_oauth_id = result[0]

                # 2. Privacy Check
                # If the session is owned by someone else, block access
                if db_oauth_id is not None and db_oauth_id != oauth_id:
                    raise HTTPException(
                        status_code=403, 
                        detail="❌ Access Denied !!"
                    )
                
                return True

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"🔴Database error in verify_session: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error to verify session")