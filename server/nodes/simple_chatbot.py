import logging

from state.state import State
from modules.llm import get_chatbot_prompt

logger = logging.getLogger(__name__)


async def simple_chatbot_node(
    state: State,
    llm_factory,
):
    """
    Lightweight direct-response chatbot.

    Used for:
    - greetings
    - coding questions
    - explanations
    - casual chat
    - unsupported requests

    Does NOT use retrieval context.
    """

    try:
        llm = llm_factory()

        prompt = get_chatbot_prompt()
        chain = prompt | llm

        recent_messages = state.get("messages", [])[-8:]

        response = await chain.ainvoke({
            "messages": recent_messages,
        })

        state["messages"].append(response)
        state["route"] = "end"

        logger.info("Simple chatbot response generated.")

        return state

    except Exception as e:
        logger.error(f"Simple chatbot node error: {e}")

        state["route"] = "end"

        return state