# import logging
# from state.state import State
# from modules.llm import get_chatbot_prompt

# logger = logging.getLogger(__name__)

# async def chatbot_node(state: State, llm_runnable_factory):
#     llm = llm_runnable_factory()
#     prompt = get_chatbot_prompt()

#     chain = prompt | llm

#     response = await chain.ainvoke({
#         # "summary": state.get("summary", ""),
#         "messages": state.get("messages", [])[-5:],
#     })

#     return {"messages": [response]}

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

    # -------------------------
    # State mutation (CRITICAL)
    # -------------------------

    # 1. Append assistant message
    state["messages"].append(response)

    # 2. Initialize counter defensively
    state["tool_steps"] = state.get("tool_steps", 0) + 1

    # 3. Loop guard
    if state["tool_steps"] > 3:
        logger.warning("Tool loop limit reached, forcing termination")
        state["route"] = "end"

    # 4. Decide next step
    elif getattr(response, "tool_calls", None):
        state["route"] = "tools"

    else:
        state["route"] = "end"

    return state
