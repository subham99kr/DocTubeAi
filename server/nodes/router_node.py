from state.state import State
import logging
import re

logger = logging.getLogger(__name__)


async def router_node(state: State, llm_factory):

    try:

        llm = llm_factory()

        recent_messages = state["messages"][-3:]

        response = await llm.ainvoke([
            {
                "role": "system",
                "content": (
                    "You are a STRICT routing classifier.\n\n"

                    "Your task is to determine whether the user's "
                    "request requires EXTERNAL RETRIEVAL.\n\n"

                    "External retrieval includes:\n"
                    "- uploaded PDFs or documents\n"
                    "- YouTube transcripts\n"
                    "- vector database search\n"
                    "- URL/webpage reading\n"
                    "- internet/web search\n"
                    "- latest/current information\n"
                    "- external verification\n\n"

                    "Route to 'tools' if the user:\n"
                    "- asks to search, check, retrieve, verify, "
                    "look up, summarize, or read external content\n"
                    "- references uploaded files, PDFs, docs, "
                    "transcripts, URLs, or websites\n"
                    "- requests latest or real-time information\n"
                    "- asks for information not present in "
                    "conversation memory\n\n"

                    "Route to 'chat' if the request can be answered "
                    "directly without retrieval.\n\n"

                    "Examples:\n"
                    "- 'Hi' -> chat\n"
                    "- 'Explain transformers' -> chat\n"
                    "- 'Debug this code' -> chat\n"
                    "- 'Check the uploaded PDF' -> tools\n"
                    "- 'Search latest NVIDIA news' -> tools\n"
                    "- 'Read this URL' -> tools\n"
                    "- 'Look at the docs for FastAPI middleware' -> tools\n\n"

                    "IMPORTANT:\n"
                    "- Coding questions are NOT automatically chat\n"
                    "- If documentation/search is required -> tools\n"
                    "- Unsupported capabilities should still route to chat\n"
                    "- When unsure, prefer chat\n\n"

                    "Respond with ONLY ONE WORD:\n"
                    "chat\n"
                    "or\n"
                    "tools"
                ),
            },
            *recent_messages,
        ])

        decision = response.content.strip().lower()
        decision = re.sub(r"<think>.*?</think>","",decision,flags=re.DOTALL,).strip()
        logger.info(f"Router decision: {decision}")

        if decision not in ("chat", "tools"):
            decision = "chat"

        logger.info(f"Router decision: {decision}")

        return {"route": decision}

    except Exception as e:

        logger.error(f"Router error: {e}")

        return {"route": "chat"}