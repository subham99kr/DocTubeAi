import logging
import re
import json
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
        "rag",
    ]


async def tool_call_node(
    state: State,
    tool_llm_factory,
):
    """
    Retrieval planning node.

    Responsibilities:
    - decide NEXT retrieval action
    - decide when retrieval is unnecessary
    - avoid repeated useless retrieval
    - route graph explicitly
    - control retrieval loops

    IMPORTANT:
    "rag" means:
        Answer directly with the RAG chatbot
        without using a retrieval tool.

    This is NOT the same as simple_chat.
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
                "Tool loop limit exceeded. "
                "Sending directly to rag_chatbot."
            )

            state["route"] = "rag"

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

        llm = tool_llm_factory()

        # =================================================
        # PLANNER
        # =================================================

        response = await llm.ainvoke(
            [
                {
                    "role": "system",
                    "content": f"""
You are a retrieval planner.

Choose exactly ONE route.

AVAILABLE ROUTES:

- vector_search
  Use this for uploaded/private knowledge.

- internet_search
  Use this for current/public information.

- web_scraper
  Use this only when the user provides a URL.

- rag
  Use this when the RAG chatbot can answer the question
  without performing any retrieval tool call.

ALREADY USED TOOLS:
{used_tools}

SCRATCHPAD:
{scratchpad}

RULES:

1. Prefer vector_search for uploaded/private knowledge.

2. Use internet_search for current/public information.

3. Use web_scraper only when a URL is present.

4. Use rag when retrieval is unnecessary.

5. Do NOT use fallback.

6. If the question can reasonably be answered from the
   conversation or the RAG model's existing knowledge,
   choose rag.

7. Avoid repeating tools already used unless absolutely required.

8. Return ONLY valid JSON.

FORMAT:

{{"route": "rag"}}

or

{{"route": "vector_search"}}

or

{{"route": "internet_search"}}

or

{{"route": "web_scraper"}}
""",
                },
                {
                    "role": "user",
                    "content": query,
                },
            ]
        )

        content = response.content.strip()

        # =================================================
        # PARSE ROUTE
        # =================================================

        try:
            result = json.loads(content)

            detected_route = result.get(
                "route",
                "rag",
            )

        except (
            json.JSONDecodeError,
            AttributeError,
            TypeError,
        ):

            logger.warning(
                f"Invalid planner response: {content}"
            )

            # IMPORTANT:
            # Planner failure should NOT send us to
            # simple_chat. RAG chatbot is the correct
            # fallback for this branch.

            detected_route = "rag"

        # =================================================
        # VALID ROUTES
        # =================================================

        valid_routes = {
            "vector_search",
            "internet_search",
            "web_scraper",
            "rag",
        }

        if detected_route not in valid_routes:

            logger.warning(
                f"Unknown planner route: {detected_route}. "
                f"Using rag."
            )

            detected_route = "rag"

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
                    "but no URL found. "
                    "Falling back to rag."
                )

                detected_route = "rag"

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

            if remaining:

                detected_route = remaining[0]

            else:

                # IMPORTANT:
                # No retrieval tool left.
                # Do NOT go to simple_chat.
                #
                # Let rag_chatbot answer using whatever
                # context is already available.

                detected_route = "rag"

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

        # IMPORTANT:
        # Even planner failure should remain in the
        # RAG branch because this router was already
        # selected as the RAG/tool workflow.

        state["route"] = "rag"

        return state