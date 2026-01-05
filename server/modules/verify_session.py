from global_modules.pg_pool import get_pg_pool
from fastapi import HTTPException
from typing import Optional
import logging

logger = logging.getLogger(__name__)

async def verify_and_initialize_session(session_id: str, oauth_id: Optional[str] = None, user_message: Optional[str] = None):
    pool = await get_pg_pool()
    
    upsert_query = """
        INSERT INTO sessions (session_id, oauth_id, last_activity)
        VALUES (%s, %s, NOW())
        ON CONFLICT (session_id) 
        DO UPDATE SET last_activity = NOW()
        RETURNING oauth_id, title;
    """
    
    title_update = """
        UPDATE sessions 
        SET title = %s 
        WHERE session_id = %s 
          AND title IS NULL;
    """

    try:
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                # 1. Execute UPSERT
                await cur.execute(upsert_query, (session_id, oauth_id))
                result = await cur.fetchone()
                
                if not result:
                    raise HTTPException(status_code=500, detail="Session initialization failed.")

                # result is now a tuple/row: (oauth_id, title)
                db_oauth_id, db_title = result

                # 2. Privacy Check
                if db_oauth_id is not None and db_oauth_id != oauth_id:
                    raise HTTPException(
                        status_code=403, 
                        detail="❌ Access Denied: This session is private."
                    )

                # 3. Conditional Title Update
                # Only run if db_title is NULL and we actually have a message to set
                if not db_title and user_message:
                    # We don't fetchone() here because UPDATE doesn't return data
                    await cur.execute(title_update, (user_message[:100], session_id))
                
                return True

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"🔴 Database error in verify_session: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error during session verification")