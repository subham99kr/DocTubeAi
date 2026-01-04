import logging
from typing import List, Dict
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from global_modules.pg_pool import get_pg_pool

logger = logging.getLogger(__name__)

async def get_chat_history(session_id: str) -> List[Dict[str, str]]:
    """
    Fetches filtered Human/AI chat history from the Postgres checkpointer.
    """
    chat_history = []
    
    try:
        # 1. Get the shared pool
        pool = await get_pg_pool()
        
        # 2. Initialize the saver
        saver = AsyncPostgresSaver(pool)
        config = {"configurable": {"thread_id": session_id}}

        # 3. Fetch from DB
        checkpoint_tuple = await saver.aget_tuple(config)

        if not checkpoint_tuple:
            logger.info(f"No chat history found for session: {session_id}")
            return []

        # 4. Extract messages
        checkpoint = checkpoint_tuple.checkpoint
        messages = checkpoint.get("channel_values", {}).get("messages", [])

        # 5. Filter and Format
        for msg in messages:
            if msg.type in ['human', 'ai'] and msg.content.strip():
                chat_history.append({
                    "role": "user" if msg.type == "human" else "assistant",
                    "content": msg.content.strip()
                })

        return chat_history

    except Exception as e:
        logger.error(f"Error fetching history for {session_id}: {str(e)}", exc_info=True)
        return []