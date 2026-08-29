"""
DocTubeAI graph runtime adapter.

This module exposes the existing DocTubeAI graph runtime
to application-specific integrations such as the voice system.

It does NOT create a second graph.

It reuses the same singleton graph, Tavily client and
initial-state contract used by the normal chat workflow.
"""

import logging
import os

from global_modules.pg_pool import get_pg_pool
from graph.graph_builder import RAGGraphBuilder
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from tavily import AsyncTavilyClient

from modules.llm import (
    get_rag_model,
    get_router_model,
    get_simple_chat_model,
    get_tool_model,
)

logger = logging.getLogger(__name__)


# ============================================================
# GLOBAL SINGLETONS
# ============================================================

_CHECKPOINTER = None
_COMPILED_GRAPH = None
_TAVILY_CLIENT = None


# ============================================================
# INITIAL STATE
# ============================================================


def build_initial_state(
    query: str,
) -> dict:

    return {
        "messages": [HumanMessage(content=query)],
        "query": query,
        "route": "",
        "tool_steps": 0,
        "retrieval_complete": False,
        "used_tools": [],
        "next_tool_hint": "",
        "agent_scratchpad": [],
        "retrieved_chunks": [],
        "reranked_chunks": [],
        "selected_chunks": [],
        "tool_outputs": [],
        "sources_used": [],
    }


# ============================================================
# GLOBAL INIT
# ============================================================


async def global_init():

    global _CHECKPOINTER, _COMPILED_GRAPH, _TAVILY_CLIENT

    # --------------------------------------------------------
    # Tavily singleton
    # --------------------------------------------------------

    if _TAVILY_CLIENT is None:
        _TAVILY_CLIENT = AsyncTavilyClient(os.getenv("TAVILY_API_KEY"))

        logger.info("✅ Tavily Client Initialized")

    # --------------------------------------------------------
    # Postgres pool
    # --------------------------------------------------------

    pool = await get_pg_pool()

    # --------------------------------------------------------
    # Graph singleton
    # --------------------------------------------------------

    if _COMPILED_GRAPH is None:
        _CHECKPOINTER = AsyncPostgresSaver(pool)

        builder = RAGGraphBuilder(
            router_llm_factory=(get_router_model),
            simple_chat_llm_factory=(get_simple_chat_model),
            tool_llm_factory=(get_tool_model),
            rag_llm_factory=(get_rag_model),
        )

        _COMPILED_GRAPH = builder.compile(checkpointer=_CHECKPOINTER)

        logger.info("✅ LangGraph Compiled")

    return _COMPILED_GRAPH


# ============================================================
# TAVILY
# ============================================================


def get_tavily_client():

    if _TAVILY_CLIENT is None:
        raise RuntimeError(
            "Tavily client has not been initialized. Call global_init() first."
        )

    return _TAVILY_CLIENT
