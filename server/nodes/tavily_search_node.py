import logging

from state.state import State

from tools.tavily_search import (
    run_tavily_search,
)

logger = logging.getLogger(__name__)


async def internet_search_node(
    state: State,
    config,
):

    query = state["query"]

    configurable = config.get(
        "configurable",
        {},
    )

    client = configurable.get(
        "tavily_client",
    )

    try:

        logger.info(f"🌐 Internet search: "f"{query}")

        context = await run_tavily_search(
            client,
            query,
        )

        state["used_tools"].append(
            "internet_search"
        )

        if not context:

            state["tool_outputs"].append({
                "tool": "internet_search",
                "success": False,
                "summary": (
                    "No internet search "
                    "results found."
                ),
            })

            state["agent_scratchpad"].append(
                "Internet search returned "
                "no useful results."
            )

            return state

        chunk = {
            "source_type": "internet",
            "source_name": "tavily",
            "content": context,
        }

        state["retrieved_chunks"].append(
            chunk
        )

        state["tool_outputs"].append({
            "tool": "internet_search",
            "success": True,
            "summary": (
                "Retrieved internet "
                "search results."
            ),
        })

        state["agent_scratchpad"].append(
            "Internet search retrieved "
            "external web information."
        )

        state["sources_used"].append(
            "internet"
        )

        return state

    except Exception as e:

        logger.error(
            f"❌ Internet search failed: "
            f"{str(e)}",
            exc_info=True,
        )

        state["tool_outputs"].append({
            "tool": "internet_search",
            "success": False,
            "summary": (
                "Internet search failed."
            ),
        })

        return state