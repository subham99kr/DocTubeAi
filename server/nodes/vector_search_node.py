import logging

from state.state import State

from tools.vector_search import (
    run_vector_search,
)

logger = logging.getLogger(__name__)


async def vector_search_node(
    state: State,
    config,
):

    query = state["query"]

    configurable = config.get(
        "configurable",
        {},
    )

    session_id = configurable.get(
        "session_id",
    )

    try:

        logger.info(
            f"📚 Vector search "
            f"for session: {session_id}"
        )

        context = await run_vector_search(
            query,
            session_id,
        )

        state["used_tools"].append(
            "vector_search"
        )

        if not context:

            state["tool_outputs"].append({
                "tool": "vector_search",
                "success": False,
                "summary": (
                    "No relevant vector "
                    "results found."
                ),
            })

            state["agent_scratchpad"].append(
                "Vector search returned "
                "no useful context."
            )

            return state

        chunk = {
            "source_type": "vector_db",
            "source_name": "user_documents",
            "content": context,
        }

        state["retrieved_chunks"].append(
            chunk
        )

        state["tool_outputs"].append({
            "tool": "vector_search",
            "success": True,
            "summary": (
                "Retrieved vector "
                "database context."
            ),
        })

        state["agent_scratchpad"].append(
            "Vector search retrieved "
            "relevant document context."
        )

        state["sources_used"].append(
            "vector_db"
        )

        return state

    except Exception as e:

        logger.error(
            f"❌ Vector search failed: "
            f"{str(e)}",
            exc_info=True,
        )

        state["tool_outputs"].append({
            "tool": "vector_search",
            "success": False,
            "summary": (
                "Vector search failed."
            ),
        })

        return state