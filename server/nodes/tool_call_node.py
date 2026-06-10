import logging
import re
from typing import Literal

from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from state.state import State

logger = logging.getLogger(__name__)


class ToolDecision(BaseModel):
    route: Literal[
        "vector_search",
        "internet_search",
        "web_scraper",
        "fallback",
    ]


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
            m
            for m in reversed(state["messages"])
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

        llm = (
            tool_llm_factory()
            .with_structured_output(
                ToolDecision
            )
        )

        # =================================================
        # PLANNER
        # =================================================

        response = await llm.ainvoke([
            {
                "role": "system",
                "content": f"""
You are a retrieval planner.

Choose exactly one route.

AVAILABLE ROUTES:
- vector_search
- internet_search
- web_scraper
- fallback

ALREADY USED TOOLS:
{used_tools}

SCRATCHPAD:
{scratchpad}

RULES:
1. Prefer vector_search for uploaded/private knowledge.
2. Use internet_search for current/public information.
3. Use web_scraper only when a URL is present.
4. Use fallback when retrieval is unnecessary.
5. Avoid repeating tools already used unless absolutely required.
"""
            },
            {
                "role": "user",
                "content": query,
            },
        ])

        detected_route = response.route

        # =================================================
        # URL VALIDATION
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
                    "web_scraper selected "
                    "but no URL found."
                )

                detected_route = (
                    "internet_search"
                )

        # =================================================
        # LOOP PREVENTION
        # =================================================

        if detected_route in used_tools:

            logger.warning(
                f"Repeated tool attempt: "
                f"{detected_route}"
            )

            remaining = [
                route
                for route in [
                    "vector_search",
                    "internet_search",
                    "web_scraper",
                ]
                if route not in used_tools
            ]

            detected_route = (
                remaining[0]
                if remaining
                else "fallback"
            )

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