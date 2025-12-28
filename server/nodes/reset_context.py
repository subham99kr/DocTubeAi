from state.state import State

async def reset_context_node(state: State) -> dict:
    """
    Graph Node: Resets tool-related context keys to empty strings.
    This will prevents "Context Poisoning" where data from a previous turn 
    interferes with the LLM's reasoning for the current question.
    """
    return {
        "vector_context": "",
        "scraped_text": "",
        "web_results": "",
    }