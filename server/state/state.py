from typing import TypedDict, Annotated, Sequence
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage 


class State(TypedDict):
     
    # Core Components
    messages: Annotated[Sequence[BaseMessage], add_messages]
    summary: str
    
    # 2. Steps: Useful for debugging which nodes actually ran
    # intermediate_steps: Annotated[List[str], operator.add]
    
    