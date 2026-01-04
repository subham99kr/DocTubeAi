from langchain_core.messages import HumanMessage, AIMessage
from state.state import State
import logging
logger = logging.getLogger(__name__)

async def summary_node(state: State, summary_llm):
    """
    Updates the conversation summary by incorporating the most recent turn.
    """
    old_summary = state.get("summary", "")
    messages = state.get("messages", [])

    if len(messages) < 2:
        return {}

    # 1. IDENTIFY THE LAST TURN
    # skiping internal ToolMessages to keep the summary prompt clean.
    last_human = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
    last_ai = next((m.content for m in reversed(messages) if isinstance(m, AIMessage) and not m.tool_calls), "")

    if not last_human or not last_ai:
        return {}

    # 2. CONSTRUCT THE PROMPT
    prompt = (
        f"Current Summary: {old_summary}\n"
        f"New Interaction:\n"
        f"User: {last_human}\n"
        f"AI: {last_ai}\n\n"
        "INSTRUCTIONS:\n"
        "- You have to summarize it , keep things under 400 words"
        "- Summarize the 'intent' of the code, not the code itself.\n"
        "- Example: Instead of 'User sent @app.get...', write 'User provided a FastAPI route for review'.\n"
        "- This keeps the memory clean for future technical questions."
    )
    
    # 3. EXECUTE
    response = await summary_llm.ainvoke(prompt)
    # logger.info(f"last ai = {last_ai}")
    # logger.info(f"summary:{response}")
    
    return {"summary": response.content}