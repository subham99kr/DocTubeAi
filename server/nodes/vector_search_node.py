

from tools.vector_search import run_vector_search
from langchain_core.runnables import RunnableConfig
from typing import Annotated
from langchain_core.tools import tool,InjectedToolArg
import logging
logger = logging.getLogger(__name__)


@tool
async def docs_or_Youtube_video_or_pdf_Search(query:str,config:RunnableConfig) -> str:
    """
    PRIMARY SEARCH TOOL. Use this FIRST for any questions about the user's 
    uploaded PDFs, documents, YouTube transcripts, youtube title . 
    This contains the private, specific knowledge the user is asking about.
    """
    
    
    session_id = config.get("configurable", {}).get("session_id")
#     collection = config.get("configurable", {}).get("mongo_collection")
#     embeddings = config.get("configurable", {}).get("embeddings")
    
    
    # We call the logic function (the tool)
    logger.info(f"Calling vector logic for session id: {session_id}")
    context = await run_vector_search(query,session_id)
    if not context:
            return "No relevant information found from the uploaded pdf(s)/youtube link(s)."

    # return {"vector_context": context}
    return context