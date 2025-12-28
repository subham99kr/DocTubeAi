

from pydantic import SkipValidation
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
    """Search the internet for news or general knowledge.
    Input: to_search:str ,skip anyother parameter
    """
    # logger.info(f"🚀 internet_search tools triggered with query: {to_search}")
    
    configurable = config.get("configurable", {})
    client = configurable.get("tavily_client")
    
    try:
        # Call the renamed logic function
        logger.info("starting the tavily logic")
        context = await run_tavily_search(client, to_search)
        return context or "No results found."
    except Exception as e:
        logger.error(f"❌ Tool execution crashed: {str(e)}", exc_info=True)
        return "An internal error occurred during search."