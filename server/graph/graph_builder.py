from typing import Any, List
from functools import partial
from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.base import BaseCheckpointSaver
from state.state import State
from nodes.chatbot import chatbot_node
from nodes.summary_node import summary_node

class RAGGraphBuilder:
    def __init__(
        self, 
        llm: Any, 
        summary_llm: Any, 
        tools: List[Any]
    ):
        self.llm = llm
        self.summary_llm = summary_llm
        
        self.tools = tools 
        self.builder = StateGraph(State)

    def _setup_nodes(self):
        # 1. Chatbot Node
        self.builder.add_node(
            "chatbot", 
            partial(chatbot_node, llm_runnable_factory=self.llm, tools=self.tools)
        )

        # 2. Tool Node
        self.builder.add_node("tools", ToolNode(self.tools))

        # 3. Summary Node
        self.builder.add_node(
            "summarize", 
            partial(summary_node, summary_llm=self.summary_llm)
        )

    def _setup_edges(self):
        # 1. Start -> Chatbot
        self.builder.add_edge(START, "chatbot")

        # 2. Chatbot -> (tools OR summarize)
        self.builder.add_conditional_edges(
            "chatbot",
            tools_condition,
            {
                "tools": "tools",
                "__end__": "summarize"   
            }
        )

        # 3. Tools -> Chatbot
        self.builder.add_edge("tools", "chatbot")

        # 4. Summarize -> End
        self.builder.add_edge("summarize", END)

    def compile(self, checkpointer: BaseCheckpointSaver = None):
        self._setup_nodes()
        self._setup_edges()
        return self.builder.compile(checkpointer=checkpointer)
