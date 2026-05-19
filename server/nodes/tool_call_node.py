import logging
import re

from langchain_core.messages import HumanMessage

from state.state import State

logger = logging.getLogger(__name__)


async def tool_call_node(
    state: State,
    tool_llm_factory,
):
    """
    Retrieval planning node.

    Responsibilities:
    - decide NEXT retrieval action
    - avoid repeated useless retrieval
    - route graph explicitly
    - control retrieval loops
    """

    try:

        # =================================================
        # LOOP PROTECTION
        # =================================================

        state["tool_steps"] = (
            state.get("tool_steps", 0) + 1
        )

        if state["tool_steps"] > 4:

            logger.warning(
                "Tool loop limit exceeded."
            )

            state["route"] = "fallback"

            return state

        # =================================================
        # QUERY
        # =================================================

        last_human = next(
            m for m in reversed(state["messages"])
            if isinstance(m, HumanMessage)
        )

        query = last_human.content

        used_tools = state.get(
            "used_tools",
            [],
        )

        scratchpad = "\n".join(
            state.get(
                "agent_scratchpad",
                [],
            )
        )

        # =================================================
        # MODEL
        # =================================================

        llm = tool_llm_factory()

        # =================================================
        # PLANNER PROMPT
        # =================================================

        response = await llm.ainvoke([
            {
                "role": "system",
                "content": f"""
                            You are a retrieval planner.

                            Your job is to decide the NEXT BEST retrieval action.

                            AVAILABLE RETRIEVAL NODES:
                            - vector_search
                            - internet_search
                            - web_scraper
                            - fallback

                            TOOLS DESCRIPTION:

                            vector_search:
                            - uploaded PDFs
                            - private docs
                            - transcripts
                            - user-uploaded knowledge

                            internet_search:
                            - latest/current information
                            - external verification
                            - public web search

                            web_scraper:
                            - reading a specific URL/webpage

                            fallback:
                            - retrieval unnecessary
                            - cannot retrieve anything useful

                            ALREADY USED TOOLS:
                            {used_tools}

                            SCRATCHPAD:
                            {scratchpad}

                            IMPORTANT RULES:
                            1. Do NOT repeatedly call the same tool unless necessary.
                            2. Prefer vector_search FIRST for uploaded/private knowledge.
                            3. Use internet_search if vector search was insufficient.
                            4. Use web_scraper ONLY if a URL is explicitly present.
                            5. Route to fallback if retrieval is unnecessary.
                            6. Return ONLY ONE WORD.

                            VALID OUTPUTS:
                            vector_search
                            internet_search
                            web_scraper
                            fallback
                            """
            },
            {
                "role": "user",
                "content": query,
            },
        ])

        # =================================================
        # CLEAN RESPONSE
        # =================================================

        decision = response.content.strip().lower()

        decision = re.sub(
            r"<think>.*?</think>",
            "",
            decision,
            flags=re.DOTALL,
        ).strip()

        # =================================================
        # NORMALIZATION
        # =================================================

        valid_routes = [
            "vector_search",
            "internet_search",
            "web_scraper",
            "fallback",
        ]

        detected_route = None

        for route in valid_routes:

            if route in decision:
                detected_route = route
                break

        if detected_route is None:
            detected_route = "fallback"

        # =================================================
        # URL EXTRACTION
        # =================================================

        if detected_route == "web_scraper":

            url_match = re.search(
                r"https?://\S+",
                query,
            )

            if url_match:

                state["next_tool_hint"] = (
                    url_match.group(0)
                )

            else:

                logger.warning(
                    "Planner selected "
                    "web_scraper but "
                    "no URL found."
                )

                detected_route = (
                    "internet_search"
                )

        # =================================================
        # PREVENT SAME TOOL LOOPS
        # =================================================

        if (detected_route in used_tools):

            logger.warning(
                f"Planner attempted "
                f"repeated tool: "
                f"{detected_route}"
            )

            remaining = [
                "vector_search",
                "internet_search",
                "web_scraper",
            ]

            remaining = [
                r for r in remaining
                if r not in used_tools
            ]

            if remaining:

                detected_route = (
                    remaining[0]
                )

            else:

                detected_route = "fallback"

        # =================================================
        # SAVE ROUTE
        # =================================================

        state["route"] = detected_route

        logger.info(
            f"Planner selected route: "
            f"{detected_route}"
        )

        return state

    except Exception as e:

        logger.error(
            f"Tool planner error: {str(e)}",
            exc_info=True,
        )

        state["route"] = "fallback"

        return state