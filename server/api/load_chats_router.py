from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List,Dict
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from global_modules.pg_pool import get_pg_pool
from modules.verify_session import verify_and_initialize_session
from auth.dependencies import get_current_user_optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chats",
    tags=["Chats"]
)

class ChatMessage(BaseModel):
    role: str
    content: str

class HistoryResponse(BaseModel):
    session_id: str = []
    history: List[ChatMessage] = []
    pdfs_uploaded: List[str] = []
    url_links: List[Dict[str, str]] = []
    
@router.get("/history/{session_id}", response_model=HistoryResponse)
async def get_chat_history(
    session_id: str,
    oauth_id: str = Depends(get_current_user_optional)
):
    # 1. Verification logic (Keep this for security)
    await verify_and_initialize_session(session_id, oauth_id)

    # Initialize empty containers for metadata
    pdfs, urls, formatted_history = [], [], []

    try:
        pool = await get_pg_pool()
        
        # 2. Fetch Session Metadata (PDFs & URLs)
        meta_query = """
            SELECT pdfs_uploaded, url_links 
            FROM sessions 
            WHERE session_id = %s AND oauth_id = %s;
        """
        async with pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(meta_query, (session_id, oauth_id))
                row = await cur.fetchone()
                if row:
                    pdfs = list(row[0]) if row[0] else []
                    urls = row[1] if row[1] else []

        # 3. Fetch Chat History (LangGraph Checkpoint)
        saver = AsyncPostgresSaver(pool)
        checkpoint_tuple = await saver.aget_tuple({"configurable": {"thread_id": session_id}})

        if checkpoint_tuple:
            raw_messages = checkpoint_tuple.checkpoint.get("channel_values", {}).get("messages", [])
            formatted_history = [
                ChatMessage(
                    role="user" if msg.type == "human" else "assistant",
                    content=msg.content.strip()
                )
                for msg in raw_messages 
                if msg.type in ['human', 'ai'] and msg.content.strip()
            ]

        # 4. Always return a valid object, even if lists are empty
        return HistoryResponse(
            session_id=session_id,
            history=formatted_history,
            pdfs_uploaded=pdfs,
            url_links=urls
        )

    except Exception as e:
        logger.error(f"Error in get_chat_history for {session_id}: {str(e)}")
        # Even on internal error, we return an empty state instead of crashing 500 if preferred
        return HistoryResponse(session_id=session_id)