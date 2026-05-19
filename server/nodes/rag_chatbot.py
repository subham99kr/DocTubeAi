import logging

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
)

from state.state import State
from modules.llm import get_chatbot_prompt

logger = logging.getLogger(__name__)


# =====================================================
# CONTEXT LIMITS
# =====================================================

MAX_CHUNKS = 3

MAX_TOTAL_CONTEXT = 3000

MAX_MESSAGE_HISTORY = 4

MAX_MESSAGE_SIZE = 500

MAX_OUTPUT_TOKENS = 2000

SOURCE_LIMITS = {
    "vector_db": 1000,
    "internet": 700,
    "webpage": 800,
    "unknown": 500,
}


async def rag_chatbot_node(
    state: State,
    llm_factory,
):
    """
    Final RAG synthesis chatbot.

    Responsibilities:
    - grounded answering
    - evidence synthesis
    - multi-source reasoning
    - contradiction handling
    """

    try:

        # =================================================
        # LLM
        # =================================================

        llm = llm_factory().bind(
            max_tokens=MAX_OUTPUT_TOKENS
        )

        prompt = get_chatbot_prompt()

        chain = prompt | llm

        # =================================================
        # CLEAN RECENT CONVERSATION MEMORY
        # =================================================

        recent_messages = []

        raw_messages = state.get(
            "messages",
            [],
        )[-MAX_MESSAGE_HISTORY:]

        for msg in raw_messages:

            content = getattr(
                msg,
                "content",
                "",
            )

            content = str(content)[
                :MAX_MESSAGE_SIZE
            ]

            if isinstance(
                msg,
                HumanMessage,
            ):

                recent_messages.append(
                    HumanMessage(
                        content=content
                    )
                )

            elif isinstance(
                msg,
                AIMessage,
            ):

                recent_messages.append(
                    AIMessage(
                        content=content
                    )
                )

        # =================================================
        # RETRIEVED CHUNKS
        # =================================================

        selected_chunks = state.get(
            "selected_chunks",
            [],
        )[:MAX_CHUNKS]

        # =================================================
        # BUILD COMPRESSED RAG CONTEXT
        # =================================================

        rag_context = []

        current_context_size = 0

        for idx, chunk in enumerate(
            selected_chunks
        ):

            source_type = chunk.get(
                "source_type",
                "unknown",
            )

            source_name = chunk.get(
                "source_name",
                "unknown",
            )

            text = chunk.get(
                "content",
                "",
            )

            # ---------------------------------------------
            # SOURCE LIMITS
            # ---------------------------------------------

            char_limit = SOURCE_LIMITS.get(
                source_type,
                SOURCE_LIMITS["unknown"],
            )

            text = text[:char_limit]

            # ---------------------------------------------
            # GLOBAL CONTEXT BUDGET
            # ---------------------------------------------

            if (
                current_context_size + len(text)
                > MAX_TOTAL_CONTEXT
            ):
                break

            current_context_size += len(
                text
            )

            rag_context.append(
                f"""
SOURCE {idx + 1}
TYPE: {source_type}
NAME: {source_name}

CONTENT:
{text}
"""
            )

        final_context = "\n\n".join(
            rag_context
        )

        # =================================================
        # BUILD TEMPORARY ENHANCED QUERY
        # =================================================

        enhanced_messages = list(
            recent_messages
        )

        if (
            final_context
            and enhanced_messages
        ):

            last_message = (
                enhanced_messages[-1]
            )

            if hasattr(
                last_message,
                "content",
            ):

                original_query = (
                    last_message.content
                )

                enhanced_query = f"""
Answer the user's question using the retrieved evidence.

================ RETRIEVED EVIDENCE ================

{final_context}

================ USER QUERY ================

{original_query}
"""

                # IMPORTANT:
                # Do NOT mutate original memory

                enhanced_messages = (
                    enhanced_messages[:-1]
                    + [
                        HumanMessage(
                            content=enhanced_query
                        )
                    ]
                )

        # =================================================
        # DEBUG LOGGING
        # =================================================

        logger.info(
            f"Total messages: {len(enhanced_messages)}"
        )

        total_chars = 0

        for idx, msg in enumerate(
            enhanced_messages
        ):

            content = getattr(
                msg,
                "content",
                "",
            )

            size = len(str(content))

            total_chars += size

            logger.info(
                f"Message {idx} size: {size}"
            )

        logger.info(
            f"Total prompt chars: {total_chars}"
        )

        # =================================================
        # GENERATE RESPONSE
        # =================================================

        response = await chain.ainvoke({
            "messages": enhanced_messages,
        })

        # =================================================
        # SAVE RESPONSE
        # =================================================

        state["messages"].append(
            response
        )

        state["route"] = "end"

        logger.info(
            "RAG chatbot response generated."
        )

        return state

    except Exception as e:

        logger.error(
            f"RAG chatbot node error: {e}",
            exc_info=True,
        )

        state["route"] = "end"

        return state