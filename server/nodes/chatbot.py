from state.state import State
from modules.llm import get_chatbot_prompt
from langchain_core.messages import HumanMessage, AIMessage,ToolMessage
import logging
logger  = logging.getLogger(__name__)

async def chatbot_node(state: State, llm_runnable_factory, tools):
    summary = state.get("summary", "")
    
    # 1. DO NOT filter out ToolMessages or AIMessages manually.
    # The LLM needs the full sequence of the current conversation turn.
    # Just take the last 10 messages to keep the context window manageable.
    messages = state["messages"]
    context_window = messages[-5:] 

    # 2. Bind tools
    # Since you aren't passing clients anymore, this should be stable.
    llm = llm_runnable_factory().bind_tools(tools)
    prompt = get_chatbot_prompt()
    chain = prompt | llm
    
    # 3. Invoke
    response = await chain.ainvoke({
        "summary": summary,
        "messages": context_window 
    })
    
    # Log for debugging
    tool_calls = getattr(response, "tool_calls", None)
    if tool_calls:
        logger.info(f"🎯 LLM requested tools: {[t['name'] for t in response.tool_calls]}")
    else:
        logger.info("ℹ️ LLM did not request any tools. It responded directly.")
    
    return {"messages": [response]}


# from typing import Dict, Any
# from langchain_core.messages import AIMessage

# async def chatbot_node(state: State, llm_runnable_factory: Any) -> Dict:
#     """
#     Graph Node: Generates a response using the main reasoning LLM.
    
#     Args:
#         state: The current graph state.
#         llm_runnable_factory: The function 'get_llm_runnable' passed via injection.
#     """
    
#     # 1. Get the compiled LCEL chain (prompt | model | parser)
#     chain = llm_runnable_factory()
    
#     # 2. Invoke the chain with the current state.
#     response_text = await chain.ainvoke(state)
    
#     # 3. Update the state
#     # We return an AIMessage for the history and the raw answer for the final response.
#     return {
#         "messages": [AIMessage(content=response_text)],
#         "answer": response_text
#     }