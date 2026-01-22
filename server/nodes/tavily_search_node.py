from langchain_core.tools import tool
from tools.tavily_search import run_tavily_search 
from langchain_core.runnables import RunnableConfig
import logging

logger = logging.getLogger(__name__)

@tool
async def internet_search(
    to_search: str, 
    config: RunnableConfig
) -> str:
    """
    USE THIS ONLY AS A LAST RESORT. 
    If the user asks about specific files, transcripts, or uploaded content, 
    you MUST use 'docs_or_Youtube_video_or_pdf_Search' first.
    Only use this if the local search returns 'No relevant information found' 
    or if the question is about current world events (e.g., today's news).
    """
    # logger.info(f"🚀 internet_search tools triggered with query: {to_search}")
    
    configurable = config.get("configurable", {})
    client = configurable.get("tavily_client")
    
    try:
        # Call the renamed logic function
        logger.info("starting the tavily logic")
        context = await run_tavily_search(client, to_search)
        return f"[INTERNET_SEARCH]\n{context}" if context else "[INTERNET_SEARCH]\nNo results found."
    except Exception as e:
        logger.error(f"❌ Tool execution crashed: {str(e)}", exc_info=True)
        return "An internal error occurred during search."