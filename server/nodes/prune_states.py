from state.state import State

async def prune_state_node(
    state: State,
) -> State:
    """
    Cleanup transient workflow state.

    Preserves:
    - conversation messages

    Clears:
    - retrieval artifacts
    - planner memory
    - execution metadata
    """
    # -----------------------------------------
    # Routing / execution
    # -----------------------------------------
    state["route"] = ""
    state["tool_steps"] = 0
    state["retrieval_complete"] = False
    state["next_tool_hint"] = ""
    # -----------------------------------------
    # Retrieval memory
    # -----------------------------------------
    state["retrieved_chunks"] = []
    state["reranked_chunks"] = []
    state["selected_chunks"] = []
    # -----------------------------------------
    # Agent memory
    # -----------------------------------------
    state["used_tools"] = []
    state["agent_scratchpad"] = []
    state["tool_outputs"] = []
    state["sources_used"] = []
    return state