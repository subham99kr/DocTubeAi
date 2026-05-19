from state.state import State
import asyncio
from global_modules.reranker import (
    get_reranker,
)


async def reranker_node(state: State):

    reranker = get_reranker()

    query = state["query"]

    chunks = state.get(
        "retrieved_chunks",
        [],
    )

    if not chunks:

        state["reranked_chunks"] = []

        return state

    pairs = [
        (query, chunk.get("content", ""))
        for chunk in chunks
    ]

    scores = await asyncio.to_thread(
                reranker.predict,
                pairs,
            )

    ranked = []

    for chunk, score in zip(chunks, scores):

        chunk["rerank_score"] = float(score)

        ranked.append(chunk)

    ranked.sort(
        key=lambda x: x["rerank_score"],
        reverse=True,
    )

    state["reranked_chunks"] = ranked

    state["selected_chunks"] = ranked[:4]

    return state