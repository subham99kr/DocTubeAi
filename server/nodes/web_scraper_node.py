# from langchain_core.runnables import RunnableConfig
from pydantic import SkipValidation
from langchain_core.tools import tool
from tools.web_scraper import run_web_scrape
import logging
logger = logging.getLogger(__name__)
from langchain_core.runnables import RunnableConfig

@tool
async def web_scraper_node(url:str,config:RunnableConfig) -> SkipValidation[str]:
    """
    This is a web scraper it get the text from a website if provided the url.
    """
    try:
        http_client = config.get("configurable", {}).get("http_client")
        logger.info(f"calling logic for {url}")
        content = await run_web_scrape(url,http_client)
        # logger.info(f"content retrived {content}")
        return str(content)
    except Exception as e:
        logger.error(f"Scraper failed for {url}: {str(e)}")
        return f"Error: Could not retrieve content from {url}."
