from typing import Any, List
from functools import partial

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode
from langgraph.checkpoint.base import BaseCheckpointSaver

from state.state import State
from nodes.router_node import router_node
from nodes.tool_call_node import tool_call_node
from nodes.chatbot import chatbot_node

from nodes.prune_states import prune_state_node



class RAGGraphBuilder:
    def __init__(
        self,
        chat_llm_factory: Any,
        tool_llm_factory: Any,
        tools: List[Any],
    ):
        self.chat_llm_factory = chat_llm_factory
        self.tool_llm_factory = tool_llm_factory
        self.tools = tools
        self.builder = StateGraph(State)

    def _setup_nodes(self):
        self.builder.add_node(
            "router",
            partial(router_node, llm_factory=self.chat_llm_factory),
        )

        self.builder.add_node(
            "tool_call",
            partial(
                tool_call_node,
                tool_llm_factory=self.tool_llm_factory,
                tools=self.tools,
            ),
        )

        self.builder.add_node("tools", ToolNode(self.tools))

        self.builder.add_node(
            "chatbot",
            partial(chatbot_node, llm_runnable_factory=self.chat_llm_factory),
        )

        self.builder.add_node("prune", prune_state_node)

        

    def _setup_edges(self):
        self.builder.add_edge(START, "router")

        self.builder.add_conditional_edges(
            "router",
            # lambda s: s["route"],
            lambda s: s.get("route", "chat"),
            {
                "tools": "tool_call",
                "chat": "chatbot",
            },
        )

        self.builder.add_edge("tool_call", "tools")
        self.builder.add_edge("chatbot", "prune")
        # self.builder.add_edge("chatbot", END)
        self.builder.add_conditional_edges(
            "tools",
            lambda s: s.get("route", "end"),
            {
                "tools": "tool_call",
                "end": "chatbot",         # finish
            },
        )
        self.builder.add_edge("prune", END)


    def compile(self, checkpointer: BaseCheckpointSaver = None):
        self._setup_nodes()
        self._setup_edges()
        return self.builder.compile(checkpointer=checkpointer)
