from langchain_core.messages import HumanMessage
from state.state import State

async def tool_call_node(state: State, tool_llm_factory, tools):
    """
    Tool-only node.
    Groq-safe.
    """

    # 🔑 Extract ONLY the last human message
    last_human = next(
        m for m in reversed(state["messages"])
        if isinstance(m, HumanMessage)
    )

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

    if not getattr(response, "tool_calls", None):
        raise RuntimeError(
            "ToolCallNode failed: model did not emit tool_calls"
        )

    return {"messages": [response]}
