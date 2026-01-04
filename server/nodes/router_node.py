from state.state import State

async def router_node(state: State, llm_factory):
    """
    LLM-only router.
    NO tools bound.
    Must output ONLY 'chat' or 'tools'.
    """

    llm = llm_factory()

    last_human = state["messages"][-1].content

    response = await llm.ainvoke([
        {
            "role": "system",
            "content": (
                "You are a routing classifier.\n\n"
                "Decide whether the user's query requires EXTERNAL INFORMATION "
                "(web search, PDFs, documents, latest data).\n\n"
                "Rules:\n"
                "1. If the user asks to EXPLAIN, COMMENT, REVIEW, DEBUG, or REFACTOR code → chat\n"
                "2. If the user asks for LATEST news, SEARCH, FIND, or FROM DOCUMENTS/PDFs → tools\n"
                "3. If the answer can be given directly without external sources → chat\n\n"
                "Respond with ONLY ONE WORD:\n"
                "- chat\n"
                "- tools\n"
            ),
        },
        {
            "role": "user",
            "content": last_human,
        },
    ])

    decision = response.content.strip().lower()

    # Hard safety clamp (never trust free-form output)
    if decision not in ("chat", "tools"):
        decision = "chat"

    return {"route": decision}
