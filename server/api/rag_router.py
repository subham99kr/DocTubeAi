from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

# Import the orchestrator function
from modules.ask_query import ask_with_graph 

router = APIRouter()

class RAGRequest(BaseModel):
    """
    Defines the expected request body for a RAG query.
    """
    query: str
    session_id: Optional[str] = None
    user_id: Optional[str] = None

@router.post("/ask")
async def run_rag(req: RAGRequest): 
    """
    Main endpoint for RAG queries. It routes the request through the LangGraph synchronously.
    """
    try:
        
        # Step 2: Map the Pydantic model to the dict expected by ask_with_graph
        request_obj = {
            "users_query": req.query, 
            "session_id": req.session_id,
            "oauthID": req.user_id,
        }

        # Step 3: Run the synchronous function directly
        result = await ask_with_graph(request_obj)
        
        # *** FIX: Check if the result is an error dictionary and raise HTTPException ***
        if "detail" in result:
            raise HTTPException(status_code=500, detail=result["detail"])

        # *** SUCCESS PATH ***
        # Step 4: Return the result to the user
        return {
            "answer": str(result.get("answer", "")),
            "session_id": str(result.get("session_id", "")),
            "code": int(result.get("code", 200)),
            # "summary": str(result.get("summary", "")),
        }
        
    except HTTPException as http_e:
        # Re-raise explicit HTTP exceptions
        raise http_e
    except Exception as e:
        # Catch any unexpected exceptions during request mapping or outside ask_with_graph
        raise HTTPException(status_code=500, detail=f"Request processing failed: {type(e).__name__}: {str(e)}")