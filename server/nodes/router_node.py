from state.state import State
import logging

logger = logging.getLogger(__name__)

async def router_node(state: State, llm_factory):
    """
    LLM-only router.
    NO tools bound.
    Must output ONLY 'chat' or 'tools'.
    """

    llm = llm_factory()

    recent_messages = state["messages"][-3:]

    try:
        response = await llm.ainvoke([
            {
                "role": "system",
                "content": (
                    "You are a STRICT routing classifier.\n\n"
                    "Your job is to decide whether the user's message requires FETCHING NEW EXTERNAL INFORMATION.\n\n"
                    "Definitions:\n"
                    "- External information means: web search, PDFs, documents, databases, or any source NOT already in memory.\n"
                    "- If the user is asking to elaborate, clarify, continue, or explain MORE about an existing answer, "
                    "that does NOT require external information.\n\n"
                    "Rules:\n"
                    "1. If the user asks to explain, elaborate, review, debug, refactor, or continue -> chat\n"
                    "2. If the user asks for more details, clarification, or follow-up -> tools\n"
                    "3. If the user explicitly asks to search, find, look up, retrieve, or read from documents/PDFs -> tools\n"
                    "4. If the user asks from a url or asks for latest news, current data, or information not already available -> tools\n"
                    "5. When in doubt -> chat\n"
                    "6. When asked to summarize a pdf or video -> tools\n"
                    "7. When just asked to summarize -> chat\n\n"
                    "Respond with ONLY ONE WORD:\n"
                    "- chat\n"
                    "- tools\n"
                ),
            },
            *recent_messages,
        ])

        decision = response.content.strip().lower()

        # Hard safety clamp (never trust free-form output)
        if decision not in ("chat", "tools"):
            decision = "chat"

        logging.info(f"Router decision: {decision}")
        return {"route": decision}

    except Exception as e:
        logging.error(f"Error in router node: {e}")
        return {"route": "chat"}  # Default to chat on error