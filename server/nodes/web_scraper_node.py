# web_scraper_node.py

import logging

from state.state import State

from tools.web_scraper import (
    run_web_scrape,
)

logger = logging.getLogger(__name__)


async def web_scraper_node(
    state: State,
    config,
):
    """
    Webpage retrieval node.

    Responsibilities:
    - scrape webpage content
    - store structured retrieval chunks
    - update retrieval memory
    """

    configurable = config.get(
        "configurable",
        {},
    )

    http_client = configurable.get(
        "http_client",
    )

    try:

        # =================================================
        # URL
        # =================================================

        url = state.get(
            "next_tool_hint",
            "",
        )

        if not url:

            logger.warning(
                "No URL available for "
                "web scraper."
            )

            state["tool_outputs"].append({
                "tool": "web_scraper",
                "success": False,
                "summary": (
                    "No URL provided."
                ),
            })

            return state

        # =================================================
        # SCRAPE
        # =================================================

        logger.info(
            f"🕸️ Scraping URL: {url}"
        )

        content = await run_web_scrape(
            url,
            http_client,
        )

        state["used_tools"].append(
            "web_scraper"
        )

        # =================================================
        # EMPTY CONTENT
        # =================================================

        if not content:

            state["tool_outputs"].append({
                "tool": "web_scraper",
                "success": False,
                "summary": (
                    "Web scraping returned "
                    "empty content."
                ),
            })

            state["agent_scratchpad"].append(
                "Web scraping failed to "
                "retrieve meaningful content."
            )

            return state

        # =================================================
        # STRUCTURED CHUNK
        # =================================================

        chunk = {
            "source_type": "webpage",
            "source_name": url,
            "content": content,
        }

        state["retrieved_chunks"].append(
            chunk
        )

        # =================================================
        # METADATA
        # =================================================

        state["tool_outputs"].append({
            "tool": "web_scraper",
            "success": True,
            "summary": (
                "Retrieved webpage content."
            ),
        })

        state["agent_scratchpad"].append(
            f"Successfully scraped: {url}"
        )

        state["sources_used"].append(
            url
        )

        logger.info(
            f"Web scraping successful: {url}"
        )

        return state

    except Exception as e:

        logger.error(
            f"❌ Web scraping failed: "
            f"{str(e)}",
            exc_info=True,
        )

        state["tool_outputs"].append({
            "tool": "web_scraper",
            "success": False,
            "summary": (
                "Web scraping failed."
            ),
        })

        return state