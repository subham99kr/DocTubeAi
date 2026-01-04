from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List
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
    session_id: str
    history: List[ChatMessage]

@router.get("/history/{session_id}", response_model=HistoryResponse)
async def get_chat_history(
    session_id: str,
    oauth_id: str = Depends(get_current_user_optional)
):
    """
    path: /chats/history/{session_id}

    Retrieves filtered chat history after verifying session ownership.
    """
    # 1. Security Check: Ensure this session belongs to the user (or is a valid guest session)
    await verify_and_initialize_session(session_id, oauth_id)

    try:
        pool = await get_pg_pool()
        saver = AsyncPostgresSaver(pool)
        config = {"configurable": {"thread_id": session_id}}

        # 2. Fetch the checkpoint from Postgres
        checkpoint_tuple = await saver.aget_tuple(config)

        if not checkpoint_tuple:
            return HistoryResponse(session_id=session_id, history=[])

        raw_messages = checkpoint_tuple.checkpoint.get("channel_values", {}).get("messages", [])

        # 3. Filter for display-only messages
        formatted_history = [
            ChatMessage(
                role="user" if msg.type == "human" else "assistant",
                content=msg.content.strip()
            )
            for msg in raw_messages 
            if msg.type in ['human', 'ai'] and msg.content.strip()
        ]

        return HistoryResponse(
            session_id=session_id,
            history=formatted_history
        )

    except Exception as e:
        logger.error(f"Error fetching history for {session_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")