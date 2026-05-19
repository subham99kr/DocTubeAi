# retrieval_evaluator.py

from state.state import State


async def retrieval_evaluator_node(
    state: State,
):
    """
    Evaluates retrieval quality.

    Responsibilities:
    - determine whether evidence is sufficient
    - continue retrieval if weak
    - stop retrieval if strong
    """

    chunks = state.get(
        "selected_chunks",
        [],
    )

    used_tools = state.get(
        "used_tools",
        [],
    )

    # =================================================
    # NO RETRIEVAL
    # =================================================

    if not chunks:

        # Try another tool if possible

        if "vector_search" not in used_tools:

            state["route"] = "tools"

        elif "internet_search" not in used_tools:

            state["route"] = "tools"

        else:

            state["route"] = "fallback"

        return state

    # =================================================
    # BEST SCORE
    # =================================================

    best_score = chunks[0].get(
        "rerank_score",
        0,
    )

    # =================================================
    # SUFFICIENT EVIDENCE
    # =================================================

    if best_score >= 0.45:

        state["retrieval_complete"] = True

        state["route"] = "rag"

        return state

    # =================================================
    # INSUFFICIENT EVIDENCE
    # =================================================

    remaining_tools = []

    if "vector_search" not in used_tools:
        remaining_tools.append(
            "vector_search"
        )

    if "internet_search" not in used_tools:
        remaining_tools.append(
            "internet_search"
        )

    if "web_scraper" not in used_tools:
        remaining_tools.append(
            "web_scraper"
        )

    # =================================================
    # MORE RETRIEVAL AVAILABLE
    # =================================================

    if remaining_tools:

        state["route"] = "tools"

    else:

        # No more retrieval sources left
        # Use best available evidence

        state["retrieval_complete"] = True

        state["route"] = "rag"

    return state