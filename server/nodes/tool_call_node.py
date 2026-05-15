from langchain_core.messages import HumanMessage
from state.state import State


async def tool_call_node(state: State, tool_llm_factory, tools):
    """
    Tool-only node.
    """

    # Extract ONLY the last human message
    last_human = next(
        m for m in reversed(state["messages"])
        if isinstance(m, HumanMessage)
    )

    # Initialize / increment tool loop counter
    state["tool_steps"] = state.get("tool_steps", 0) + 1

    # Hard stop for infinite tool loops
    if state["tool_steps"] > 3:
        state["route"] = "fallback"
        return state

    llm = (
        tool_llm_factory()
        .bind_tools(tools)
        .with_config({"tool_choice": "required"})
    )

    response = await llm.ainvoke([
        {
            "role": "system",
            "content": (
                "You MUST call one of the available tools.\n"
                "You are NOT allowed to answer in text.\n"
                "Return ONLY a tool call."
            ),
        },
        last_human,
    ])

    # Graceful fallback if model fails to emit tool calls
    if not getattr(response, "tool_calls", None):
        state["route"] = "fallback"
        return state

    # Append, do NOT overwrite state
    state["messages"].append(response)

    # Tell graph to execute tools
    state["route"] = "tools"

    return state