from typing import (
    TypedDict,
    Annotated,
    Sequence,
    List,
    Dict,
    Any,
)

from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class State(TypedDict):

    # Conversation memory
    messages: Annotated[
        Sequence[BaseMessage],
        add_messages,
    ]

    # Current user query
    query: str

    # Graph routing
    route: str

    # Loop protection
    tool_steps: int

    # Retrieval completion status
    retrieval_complete: bool

    # Tool tracking
    used_tools: List[str]

    next_tool_hint: str

    # Agent reasoning memory
    agent_scratchpad: List[str]

    # Raw retrievals
    retrieved_chunks: List[Dict[str, Any]]

    # Reranked retrievals
    reranked_chunks: List[Dict[str, Any]]

    # Final chunks for synthesis
    selected_chunks: List[Dict[str, Any]]

    # Tool execution summaries
    tool_outputs: List[Dict[str, Any]]

    # Source attribution
    sources_used: List[str]