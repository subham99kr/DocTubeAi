from functools import partial
from typing import Any

from langgraph.checkpoint.base import (
    BaseCheckpointSaver,
)
from langgraph.graph import (
    END,
    START,
    StateGraph,
)
from nodes.prune_states import (
    prune_state_node,
)
from nodes.rag_chatbot import (
    rag_chatbot_node,
)
from nodes.reranker_node import (
    reranker_node,
)
from nodes.retrieval_evaluator import (
    retrieval_evaluator_node,
)
from nodes.router_node import router_node
from nodes.simple_chatbot import (
    simple_chatbot_node,
)
from nodes.tavily_search_node import (
    internet_search_node,
)
from nodes.tool_call_node import tool_call_node
from nodes.vector_search_node import (
    vector_search_node,
)
from nodes.web_scraper_node import (
    web_scraper_node,
)
from state.state import State


class RAGGraphBuilder:
    def __init__(
        self,
        router_llm_factory: Any,
        simple_chat_llm_factory: Any,
        tool_llm_factory: Any,
        rag_llm_factory: Any,
    ):

        self.router_llm_factory = router_llm_factory

        self.simple_chat_llm_factory = simple_chat_llm_factory

        self.tool_llm_factory = tool_llm_factory

        self.rag_llm_factory = rag_llm_factory

        self.builder = StateGraph(State)

    # =====================================================
    # NODES
    # =====================================================

    def _setup_nodes(self):

        self.builder.add_node(
            "router",
            partial(
                router_node,
                llm_factory=(self.router_llm_factory),
            ),
        )

        self.builder.add_node(
            "simple_chat",
            partial(
                simple_chatbot_node,
                llm_factory=(self.simple_chat_llm_factory),
            ),
        )

        self.builder.add_node(
            "tool_call",
            partial(
                tool_call_node,
                tool_llm_factory=(self.tool_llm_factory),
            ),
        )

        self.builder.add_node(
            "vector_search",
            vector_search_node,
        )

        self.builder.add_node(
            "internet_search",
            internet_search_node,
        )

        self.builder.add_node(
            "web_scraper",
            web_scraper_node,
        )

        self.builder.add_node(
            "reranker",
            reranker_node,
        )

        self.builder.add_node(
            "retrieval_evaluator",
            retrieval_evaluator_node,
        )

        self.builder.add_node(
            "rag_chatbot",
            partial(
                rag_chatbot_node,
                llm_factory=(self.rag_llm_factory),
            ),
        )

        self.builder.add_node(
            "prune",
            prune_state_node,
        )

    # =====================================================
    # EDGES
    # =====================================================

    def _setup_edges(self):

        # -----------------------------------------
        # START
        # -----------------------------------------

        self.builder.add_edge(
            START,
            "router",
        )

        # -----------------------------------------
        # MAIN ROUTER
        # -----------------------------------------

        self.builder.add_conditional_edges(
            "router",
            lambda s: s.get(
                "route",
                "chat",
            ),
            {
                "chat": "simple_chat",
                "tools": "tool_call",
            },
        )

        # -----------------------------------------
        # SIMPLE CHAT
        # -----------------------------------------

        self.builder.add_edge(
            "simple_chat",
            "prune",
        )

        # -----------------------------------------
        # TOOL / RAG PLANNER
        # -----------------------------------------

        self.builder.add_conditional_edges(
            "tool_call",
            lambda s: s.get(
                "route",
                "rag",
            ),
            {
                "vector_search": "vector_search",
                "internet_search": "internet_search",
                "web_scraper": "web_scraper",
                # IMPORTANT:
                # No retrieval required.
                #
                # Go directly to RAG chatbot.
                "rag": "rag_chatbot",
                # Keep this only for backwards
                # compatibility with old state values.
                #
                # Even if some old code writes
                # "fallback", it must NOT go to
                # simple_chat.
                "fallback": "rag_chatbot",
            },
        )

        # -----------------------------------------
        # RETRIEVAL
        # -----------------------------------------

        self.builder.add_edge(
            "vector_search",
            "reranker",
        )

        self.builder.add_edge(
            "internet_search",
            "reranker",
        )

        self.builder.add_edge(
            "web_scraper",
            "reranker",
        )

        self.builder.add_edge(
            "reranker",
            "retrieval_evaluator",
        )

        # -----------------------------------------
        # RETRIEVAL EVALUATOR
        # -----------------------------------------

        self.builder.add_conditional_edges(
            "retrieval_evaluator",
            lambda s: s.get(
                "route",
                "rag",
            ),
            {
                # Retrieval is insufficient and another
                # tool may be needed.
                "tools": "tool_call",
                # Retrieval is useful OR no retrieval
                # is needed anymore.
                "rag": "rag_chatbot",
                # IMPORTANT:
                # Even evaluator fallback should use
                # rag_chatbot because RAG can answer
                # without retrieved tools.
                "fallback": "rag_chatbot",
            },
        )

        # -----------------------------------------
        # FINAL ANSWER
        # -----------------------------------------

        self.builder.add_edge(
            "rag_chatbot",
            "prune",
        )

        self.builder.add_edge(
            "prune",
            END,
        )

    # =====================================================
    # COMPILE
    # =====================================================

    def compile(
        self,
        checkpointer: BaseCheckpointSaver = None,
    ):

        self._setup_nodes()
        self._setup_edges()

        return self.builder.compile(checkpointer=checkpointer)
