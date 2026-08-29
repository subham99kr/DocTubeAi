"""
Voice → LangGraph adapter.

This module is the application-specific boundary between
the generic voice pipeline and the existing DocTubeAI
LangGraph workflow.

The voice pipeline knows nothing about:

    - graph construction
    - graph routing
    - retrieval
    - tools
    - reranking
    - evaluation
    - prompts
    - LLM selection

It only knows:

    text → graph → events

The existing DocTubeAI graph remains the source of truth.

Architecture:

    microphone
        ↓
    VAD
        ↓
    audio buffering
        ↓
    STT
        ↓
    text
        ↓
    VoiceGraphRunner
        ↓
    existing DocTubeAI graph
        ↓
    streamed graph events
        ↓
    VoiceGraphEvent
        ↓
    VoicePipeline
        ↓
    TTS
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncGenerator

from global_modules.http_client import (
    get_http_client,
)

from .graph_runtime import (
    build_initial_state,
    get_tavily_client,
    global_init,
)
from .models import (
    VoiceGraphEvent,
    VoiceGraphEventType,
)
from .voice_status import (
    VoiceStatusManager,
)

logger = logging.getLogger(__name__)


# ============================================================
# VoiceGraphRunner
# ============================================================


class VoiceGraphRunner:
    """
    Adapter between the voice pipeline and DocTubeAI graph.

    IMPORTANT:

    This class does NOT contain graph business logic.

    It simply:

        1. receives text from STT
        2. invokes the existing graph
        3. converts LangGraph events into voice-level events

    Therefore the graph remains completely reusable.
    """

    def __init__(
        self,
        graph: Any = None,
    ) -> None:

        # ----------------------------------------------------
        # Optional dependency injection.
        #
        # Useful for tests.
        # ----------------------------------------------------

        self.graph = graph

        # ----------------------------------------------------
        # Converts internal graph nodes into short user-facing
        # status messages.
        # ----------------------------------------------------

        self.status_manager = VoiceStatusManager()

    # ========================================================
    # GRAPH
    # ========================================================

    async def _get_graph(self) -> Any:
        """
        Return the existing DocTubeAI compiled graph.
        """

        # ----------------------------------------------------
        # Dependency injection for tests.
        # ----------------------------------------------------

        if self.graph is not None:
            return self.graph

        # ----------------------------------------------------
        # Production path.
        #
        # global_init() returns the SAME singleton graph.
        # ----------------------------------------------------

        self.graph = await global_init()

        return self.graph

    # ========================================================
    # GRAPH CONFIG
    # ========================================================

    async def _build_config(
        self,
        session_id: str,
    ) -> dict:
        """
        Build the configuration required by the existing
        DocTubeAI graph.

        This is the same runtime configuration used by the
        normal chat workflow.
        """

        http_client = await get_http_client()

        return {
            "configurable": {
                # ------------------------------------------------
                # Critical for PostgreSQL checkpoint persistence.
                #
                # The voice conversation and text conversation can
                # share the same session_id if desired.
                # ------------------------------------------------
                "thread_id": session_id,
                # ------------------------------------------------
                # Existing shared services.
                # ------------------------------------------------
                "tavily_client": get_tavily_client(),
                "http_client": http_client,
                "session_id": session_id,
            }
        }

    # ========================================================
    # NORMAL EXECUTION
    # ========================================================

    async def run(
        self,
        text: str,
        session_id: str,
    ) -> str:
        """
        Execute the existing DocTubeAI graph.

        Parameters
        ----------
        text:
            Text produced by speech-to-text.

        session_id:
            Conversation identifier.

        Returns
        -------
        str
            Final assistant response.

        Important
        ---------
        This method does NOT call a voice-specific prompt.

        The graph itself decides whether to use:

            simple_chat
            tool workflow
            rag_chatbot

        and therefore uses the same prompts and models as
        normal text chat.
        """

        text = text.strip()

        if not text:
            return ""

        if not session_id:
            raise ValueError("session_id is required for voice graph execution.")

        logger.info(
            "🧠 Voice → LangGraph session=%s text=%r",
            session_id,
            text,
        )

        # ----------------------------------------------------
        # Existing graph
        # ----------------------------------------------------

        graph = await self._get_graph()

        # ----------------------------------------------------
        # Existing graph configuration
        # ----------------------------------------------------

        config = await self._build_config(session_id)

        # ----------------------------------------------------
        # Existing graph state contract
        # ----------------------------------------------------

        initial_state = build_initial_state(text)

        # ----------------------------------------------------
        # Execute graph.
        # ----------------------------------------------------

        result = await graph.ainvoke(
            initial_state,
            config,
        )

        # ----------------------------------------------------
        # Extract final assistant response.
        # ----------------------------------------------------

        response = self._extract_response(result)

        logger.info(
            "✅ Voice → LangGraph completed session=%s response_length=%d",
            session_id,
            len(response),
        )

        return response

    # ========================================================
    # STREAM EXECUTION
    # ========================================================

    async def stream(
        self,
        text: str,
        session_id: str,
    ) -> AsyncGenerator[
        VoiceGraphEvent,
        None,
    ]:
        """
        Stream the existing DocTubeAI graph into voice-level
        events.

        LangGraph produces many internal events.

        Voice should NOT see all of them.

        Therefore this adapter converts:

            LangGraph event
                    ↓
            VoiceGraphEvent

        Only two event types are exposed:

            STATUS
                Short progress message.

            TEXT
                Actual assistant response text.

        Example:

            router
                ↓
            STATUS: "Understanding your request"

            vector_search
                ↓
            STATUS: "Searching your documents"

            reranker
                ↓
            STATUS: "Checking the most relevant information"

            rag_chatbot
                ↓
            TEXT: "The answer is..."
        """

        text = text.strip()

        if not text:
            return

        if not session_id:
            raise ValueError("session_id is required for voice graph execution.")

        logger.info(
            "🧠 Starting streaming Voice → LangGraph execution session=%s text=%r",
            session_id,
            text,
        )

        # ----------------------------------------------------
        # Reset status state for this assistant turn.
        # ----------------------------------------------------

        self.status_manager.reset()

        # ----------------------------------------------------
        # Existing graph.
        # ----------------------------------------------------

        graph = await self._get_graph()

        # ----------------------------------------------------
        # Existing graph configuration.
        # ----------------------------------------------------

        config = await self._build_config(session_id)

        # ----------------------------------------------------
        # Existing state contract.
        # ----------------------------------------------------

        initial_state = build_initial_state(text)

        status_event_count = 0
        text_event_count = 0

        try:
            # ------------------------------------------------
            # Stream ALL LangGraph events.
            #
            # The adapter decides which ones are exposed to
            # the voice layer.
            # ------------------------------------------------

            async for event in graph.astream_events(
                initial_state,
                config,
                version="v2",
            ):
                event_type = event.get("event")

                metadata = event.get(
                    "metadata",
                    {},
                )

                node_name = metadata.get("langgraph_node")

                # ============================================
                # STATUS EVENTS
                # ============================================

                if event_type == "on_chain_start":
                    status = self.status_manager.get_status(node_name)

                    if status:
                        status_event_count += 1

                        logger.debug(
                            "🎤 Graph status session=%s node=%s status=%r",
                            session_id,
                            node_name,
                            status,
                        )

                        yield VoiceGraphEvent(
                            type=(VoiceGraphEventType.STATUS),
                            content=status,
                        )

                # ============================================
                # FINAL ANSWER STREAM
                # ============================================

                if event_type != "on_chat_model_stream":
                    continue

                # ------------------------------------------------
                # IMPORTANT:
                #
                # Only final conversational nodes can generate
                # user-visible response text.
                #
                # Do NOT expose:
                #
                # router
                # tool planner
                # tool calls
                # retrieval
                # reranker
                # evaluator
                #
                # to TTS.
                # ------------------------------------------------

                if node_name not in (
                    "simple_chat",
                    "rag_chatbot",
                ):
                    continue

                chunk = event.get(
                    "data",
                    {},
                ).get("chunk")

                if chunk is None:
                    continue

                content = getattr(
                    chunk,
                    "content",
                    None,
                )

                if not isinstance(
                    content,
                    str,
                ):
                    continue

                if not content:
                    continue

                text_event_count += 1

                logger.debug(
                    "🎤 Graph response session=%s node=%s text=%r",
                    session_id,
                    node_name,
                    content,
                )

                yield VoiceGraphEvent(
                    type=(VoiceGraphEventType.TEXT),
                    content=content,
                )

            logger.info(
                "✅ Streaming Voice → LangGraph "
                "completed "
                "session=%s "
                "status_events=%d "
                "text_events=%d",
                session_id,
                status_event_count,
                text_event_count,
            )

        except asyncio.CancelledError:
            logger.info(
                "🛑 Voice → LangGraph stream cancelled session=%s",
                session_id,
            )

            raise

        except Exception:
            logger.exception(
                "❌ Voice → LangGraph stream failed session=%s",
                session_id,
            )

            raise

    # ========================================================
    # RESPONSE EXTRACTION
    # ========================================================

    @staticmethod
    def _extract_response(
        result: Any,
    ) -> str:
        """
        Extract the final assistant response from a completed
        LangGraph state.

        The current DocTubeAI graph stores conversational
        responses in:

            state["messages"]

        The most recent AI message without tool calls is
        treated as the final answer.
        """

        if result is None:
            return ""

        if isinstance(
            result,
            str,
        ):
            return result.strip()

        if not isinstance(
            result,
            dict,
        ):
            return str(result).strip()

        # ----------------------------------------------------
        # Prefer explicit response fields if a future graph
        # version introduces one.
        # ----------------------------------------------------

        for key in (
            "response",
            "answer",
            "output",
            "final_answer",
            "text",
        ):
            value = result.get(key)

            if isinstance(
                value,
                str,
            ):
                value = value.strip()

                if value:
                    return value

        # ----------------------------------------------------
        # Current graph contract:
        #
        # final response lives in messages.
        # ----------------------------------------------------

        messages = result.get(
            "messages",
            [],
        )

        for message in reversed(messages):
            content = getattr(
                message,
                "content",
                None,
            )

            if not isinstance(
                content,
                str,
            ):
                continue

            content = content.strip()

            if not content:
                continue

            message_type = getattr(
                message,
                "type",
                None,
            )

            # ------------------------------------------------
            # Do not return:
            #
            # HumanMessage
            # ToolMessage
            # AIMessage containing tool calls
            #
            # We only want the final conversational AI response.
            # ------------------------------------------------

            if message_type != "ai":
                continue

            if getattr(
                message,
                "tool_calls",
                None,
            ):
                continue

            return content

        logger.warning(
            "⚠️ Could not identify final assistant response from LangGraph result."
        )

        return ""
