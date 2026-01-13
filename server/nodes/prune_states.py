from state.state import State
from langchain_core.messages import HumanMessage, AIMessage

async def prune_state_node(state: State) -> State:
    """
    Keep ONLY:
    - last human message
    - last AI message
    """

    last_human = None
    last_ai = None

    for msg in reversed(state["messages"]):
        if last_ai is None and msg.type == "ai":
            last_ai = msg
        elif last_human is None and msg.type == "human":
            last_human = msg

        if last_human and last_ai:
            break

    new_messages = []
    if last_human:
        new_messages.append(last_human)
    if last_ai:
        new_messages.append(last_ai)

    return {"messages": new_messages}
