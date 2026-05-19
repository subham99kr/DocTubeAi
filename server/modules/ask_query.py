import os
import asyncio
import logging
from typing import (Dict,Any,AsyncGenerator)
from dotenv import load_dotenv

from tavily import AsyncTavilyClient

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from graph.graph_builder import RAGGraphBuilder

from modules.llm import (
    get_router_model,
    get_simple_chat_model,
    get_tool_model,
    get_rag_model,
)

from global_modules.pg_pool import  get_pg_pool
from global_modules.http_client import get_http_client


# =====================================================
# LOGGING
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format=(
        "%(asctime)s - %(name)s - "
        "%(levelname)s - "
        "[%(filename)s:%(lineno)d] - "
        "%(message)s"
    ),
)

logger = logging.getLogger(__name__)
load_dotenv()


# =====================================================
# GLOBAL SINGLETONS
# =====================================================

_CHECKPOINTER = None
_COMPILED_GRAPH = None
_TAVILY_CLIENT = None

# =====================================================
# INITIAL STATE
# =====================================================

def build_initial_state(query: str):

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


# =====================================================
# GLOBAL INIT
# =====================================================

async def global_init():

    global _CHECKPOINTER, _COMPILED_GRAPH, _TAVILY_CLIENT

    # -----------------------------------------
    # Tavily singleton
    # -----------------------------------------

    if _TAVILY_CLIENT is None:
        _TAVILY_CLIENT = AsyncTavilyClient(os.getenv("TAVILY_API_KEY"))
        logger.info("✅ Tavily Client Initialized")

    # -----------------------------------------
    # Postgres pool
    # -----------------------------------------
    pool = await get_pg_pool()

    # -----------------------------------------
    # Graph singleton
    # -----------------------------------------
    if _COMPILED_GRAPH is None:
        _CHECKPOINTER = AsyncPostgresSaver(
            pool
        )

        builder = RAGGraphBuilder(
            router_llm_factory=(
                get_router_model
            ),

            simple_chat_llm_factory=(
                get_simple_chat_model
            ),

            tool_llm_factory=(
                get_tool_model
            ),

            rag_llm_factory=(
                get_rag_model
            ),
        )

        _COMPILED_GRAPH = builder.compile(
            checkpointer=_CHECKPOINTER
        )

        logger.info(
            "✅ LangGraph Compiled"
        )

    return _COMPILED_GRAPH


# =====================================================
# ASK GRAPH
# =====================================================

async def ask_with_graph(
    obj: Dict[str, Any],
) -> Dict[str, Any]:

    query = obj.get(
        "users_query",
        "",
    )

    session_id = obj.get(
        "session_id",
    )

    try:

        # -----------------------------------------
        # Validate query
        # -----------------------------------------

        if not query.strip():

            logger.warning(
                f"Empty query received "
                f"for session {session_id}"
            )

            return {
                "answer": (
                    "The query cannot "
                    "be empty."
                ),
                "code": 400,
            }

        # -----------------------------------------
        # Initialize graph
        # -----------------------------------------

        await global_init()

        http_client = await get_http_client()

        config = {
            "configurable": {
                "thread_id": session_id,

                "tavily_client":
                    _TAVILY_CLIENT,

                "http_client":
                    http_client,

                "session_id":
                    session_id,
            }
        }

        initial_state = build_initial_state(
            query
        )

        logger.info(
            f"🦜 Invoking graph "
            f"for session: {session_id}"
        )

        # -----------------------------------------
        # Execute graph
        # -----------------------------------------

        result = await asyncio.wait_for(
            _COMPILED_GRAPH.ainvoke(
                initial_state,
                config,
            ),
            timeout=90,
        )

        logger.info(
            "✅ Graph invocation successful"
        )

        # -----------------------------------------
        # Extract final answer
        # -----------------------------------------

        messages = result.get(
            "messages",
            [],
        )

        final_answer = (
            "I'm sorry, I couldn't "
            "generate a response."
        )

        for msg in reversed(messages):

            if (
                msg.type == "ai"
                and not getattr(
                    msg,
                    "tool_calls",
                    None,
                )
                and msg.content
            ):

                final_answer = (
                    msg.content
                )

                break

        return {
            "answer": final_answer,
            "session_id": session_id,
            "status": "success",
            "code": 200,
        }

    except asyncio.TimeoutError:

        logger.error(
            f"⏰ Graph timeout "
            f"for session {session_id}"
        )

        return {
            "answer": (
                "The request took too "
                "long to complete."
            ),

            "status": "timeout",

            "code": 408,
        }

    except Exception as e:

        logger.error(
            f"🔴 Error in ask_with_graph "
            f"for session {session_id}: "
            f"{str(e)}",
            exc_info=True,
        )

        return {
            "answer": (
                "An internal error "
                "occurred during processing."
            ),

            "status": "error",

            "code": 500,
        }


# =====================================================
# STREAM GRAPH
# =====================================================

async def ask_with_graph_stream(obj: Dict[str, Any]) -> AsyncGenerator[dict, None]:

    query = obj.get( "users_query","",)
    session_id = obj.get("session_id")

    await global_init()

    http_client = await get_http_client()

    config = {
        "configurable": {
            "thread_id": session_id,

            "tavily_client":
                _TAVILY_CLIENT,

            "http_client":
                http_client,

            "session_id":
                session_id,
        }
    }

    initial_state = build_initial_state(
        query
    )

    try:

        async for event in (
            _COMPILED_GRAPH.astream_events(
                initial_state,
                config,
                version="v2",
            )
        ):

            event_type = event.get(
                "event"
            )

            metadata = event.get(
                "metadata",
                {},
            )

            node_name = metadata.get(
                "langgraph_node"
            )

            # =====================================
            # NODE STATUS
            # =====================================

            if event_type in [
                "on_node_start",
                "on_chain_start",
            ]:

                mapping = {
                    "router": "Routing query...",

                    "tool_call": "Planning retrieval...",

                    "vector_search": "Searching uploaded documents...",

                    "internet_search": "Searching the internet...",

                    "web_scraper": "Reading webpage content...",

                    "reranker": "Ranking retrieved evidence...",

                    "retrieval_evaluator": "Evaluating evidence quality...",

                    "rag_chatbot": "Synthesizing response...",

                    "simple_chat": "Generating response...",
                }

                if node_name in mapping:

                    yield {
                        "type": "status",

                        "data":
                            mapping[node_name],
                    }

            # =====================================
            # TOKEN STREAMING
            # =====================================

            elif (
                event_type
                == "on_chat_model_stream"
                and node_name in [
                    "simple_chat",
                    "rag_chatbot",
                ]
            ):

                chunk = (
                    event.get(
                        "data",
                        {},
                    ).get("chunk")
                )

                if (
                    chunk
                    and chunk.content
                ):

                    yield {
                        "type": "token",

                        "data":
                            chunk.content,
                    }

            # =====================================
            # GRAPH COMPLETION
            # =====================================

            elif (
                event_type
                == "on_node_end"
                and node_name == "prune"
            ):

                yield {
                    "type": "done",

                    "data": "",
                }

                return

    except Exception as e:

        logger.error(
            f"🔴 Stream Error: {str(e)}",
            exc_info=True,
        )

        yield {
            "type": "error",

            "data": (
                "Stream encountered "
                "an error."
            ),
        }