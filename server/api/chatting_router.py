import json
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio

from modules.ask_query import ask_with_graph, ask_with_graph_stream
from modules.verify_session import verify_and_initialize_session 
from auth.dependencies import get_current_user_optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chats", tags=["Chats"])

class RAGRequest(BaseModel):
    query: str
    session_id: str 

@router.post("/ask")
async def run_rag(
    req: RAGRequest,
    oauth_id: Optional[str] = Depends(get_current_user_optional) 
): 
    """
    Standard Request-Response endpoint for RAG.
    """
    # 1. Verification
    await verify_and_initialize_session(req.session_id, oauth_id,req.query)
    
    try:
        request_obj = {
            "users_query": req.query, 
            "session_id": req.session_id,
            "oauthID": oauth_id, 
        }

        # 2. Invoke Graph logic
        result = await ask_with_graph(request_obj)
        
        if "detail" in result:
            raise HTTPException(status_code=500, detail=result["detail"])

        return {
            "answer": result.get("answer", ""),
            "session_id": req.session_id,
            "status": "success"
        }
        
    except HTTPException as http_e:
        raise http_e
    except Exception as e:
        logger.error(f"RAG Error: {str(e)}")
        raise HTTPException(status_code=500, detail="An internal error occurred during processing.")



@router.post("/ask/stream")
async def run_rag_stream(
    req: RAGRequest,
    oauth_id: Optional[str] = Depends(get_current_user_optional),
):
    await verify_and_initialize_session(req.session_id, oauth_id,req.query)

    request_obj = {
        "users_query": req.query,
        "session_id": req.session_id,
        "oauthID": oauth_id,
    }

    async def event_generator():
        # Queue to handle concurrent heartbeat and graph events
        queue = asyncio.Queue()

        async def produce_events():
            async for event in ask_with_graph_stream(request_obj):
                await queue.put(event)
            await queue.put(None)  # Sentinel to stop

        async def produce_heartbeat():
            while True:
                await asyncio.sleep(15)  # Heartbeat every 15 seconds
                await queue.put({"type": "heartbeat", "data": "keep-alive"})

        # Run both tasks
        event_task = asyncio.create_task(produce_events())
        heartbeat_task = asyncio.create_task(produce_heartbeat())

        try:
            while True:
                event = await queue.get()
                if event is None: break
                
                # Filter heartbeats in frontend or ignore them
                yield f"data: {json.dumps(event)}\n\n"
                
                # Stop heartbeat if graph is done
                if event.get("type") == "done":
                    break
        except Exception as e:
            logger.error(f"SSE Error: {e}")
            yield f"data: {json.dumps({'type': 'error', 'data': 'Stream Break'})}\n\n"
        finally:
            event_task.cancel()
            heartbeat_task.cancel()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Critical for Nginx
            "Transfer-Encoding": "chunked"
        },
    )