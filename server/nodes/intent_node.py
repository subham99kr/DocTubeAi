from state.state import State

async def intent_node(state: State, tool_llm_factory, tools):
    llm = (
        tool_llm_factory()
        .bind_tools(tools)
        .with_config({
            "tool_choice": "auto"   # 🔥 THIS LINE IS CRITICAL
        })
    )

    response = await llm.ainvoke(state["messages"])
    return {"messages": [response]}
