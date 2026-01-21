
import logging
from state.state import State
from modules.llm import get_chatbot_prompt

logger = logging.getLogger(__name__)

async def chatbot_node(state: State, llm_runnable_factory):
    llm = llm_runnable_factory()
    prompt = get_chatbot_prompt()

    chain = prompt | llm

    response = await chain.ainvoke({
        "messages": state.get("messages", [])[-5:],
    })

    state["messages"].append(response)
    state["route"] = "end"

    return state
