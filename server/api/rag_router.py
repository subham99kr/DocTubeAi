from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from fastapi.responses import StreamingResponse
import json

from modules.ask_query import ask_with_graph,ask_with_graph_stream
from modules.verify_session import verify_and_initialize_session 
from auth.dependencies import get_current_user_optional

router = APIRouter()

class RAGRequest(BaseModel):
    query: str
    session_id: str 

@router.post("/ask")
async def run_rag(
    req: RAGRequest,
    # This decrypts the JWT. If no token, oauth_id is None (Guest)
    oauth_id: Optional[str] = Depends(get_current_user_optional) 
): 
    """
    Main endpoint for RAG queries.
    """
    
    # STEP 1: Security Check
    # We use 'oauth_id' from the JWT, NOT req.user_id!
    await verify_and_initialize_session(req.session_id, oauth_id)
    
    try:
        # STEP 2: Map to the orchestrator
        # We pass the verified oauth_id here. 
        # This ensures the LLM/Database only sees the proven identity.
        request_obj = {
            "users_query": req.query, 
            "session_id": req.session_id,
            "oauthID": oauth_id, 
        }

        # STEP 3: Run the graph
        result = await ask_with_graph(request_obj)
        
        # Error handling for the result dictionary
        if "detail" in result:
            raise HTTPException(status_code=500, detail=result["detail"])

        return {
            "answer": result.get("answer", ""),
            "session_id": req.session_id,
            "code": result.get("code", 200)
        }
        
    except HTTPException as http_e:
        raise http_e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal Error: {str(e)}")

@router.post("/ask/stream")
async def run_rag_stream(
    req: RAGRequest,
    oauth_id: Optional[str] = Depends(get_current_user_optional),
):
    """
    Streaming RAG endpoint (SSE).
    """

    # STEP 1: Security
    await verify_and_initialize_session(req.session_id, oauth_id)

    request_obj = {
        "users_query": req.query,
        "session_id": req.session_id,
        "oauthID": oauth_id,
    }

    async def event_generator():
        async for event in ask_with_graph_stream(request_obj):
            # SSE format
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
