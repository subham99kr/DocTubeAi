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
    # skip internal ToolMessages to keep the summary prompt clean.
    last_human = next((m.content for m in reversed(messages) if isinstance(m, HumanMessage)), "")
    last_ai = next((m.content for m in reversed(messages) if isinstance(m, AIMessage) and not m.tool_calls), "")

    if not last_human or not last_ai:
        return {}

    # 2. CONSTRUCT THE PROMPT
    prompt = (
        f"You are a memory assistant. Update the 'Current Summary' by adding the details from the 'New Interaction'.\n\n"
        f"Current Summary: {old_summary if old_summary else 'No history yet.'}\n\n"
        f"New Interaction:\n"
        f"User said: {last_human}\n"
        f"AI responded: {last_ai}\n\n"
        "Rules:\n"
        "- Don't update if its a greeting.\n"
        "- Create a single cohesive paragraph.\n"
        "- Focus on what the user is looking for and what was found.\n"
        "- You can remove the more than 10 messages older part but keep the users details intact.\n"
        "- Keep the total summary under 300 words."
    )
    
    # 3. EXECUTE
    response = await summary_llm.ainvoke(prompt)
    # logger.info(f"last ai = {last_ai}")
    # logger.info(f"summary:{response}")
    
    return {"summary": response.content}