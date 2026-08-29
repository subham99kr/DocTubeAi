"""
Voice assistant execution boundary.

File:
    voice/assistant.py

Responsibilities:
    - Provide a small application-level boundary around assistant execution.
    - Delegate all actual graph execution to VoiceGraphRunner.
    - Support the streaming execution model used by the voice pipeline.
    - Provide a single place for assistant-level lifecycle logging.

IMPORTANT:

    This class does NOT own:
        - LangGraph construction
        - LangGraph routing
        - graph state
        - graph checkpoints
        - graph cancellation
        - token streaming
        - sentence buffering
        - TTS
        - WebSocket communication
        - VAD
        - Whisper
        - turn detection

    Those responsibilities belong to their respective layers.

Architecture:

    VoicePipeline
          |
          v
    VoiceAssistant
          |
          v
    VoiceGraphRunner
          |
          v
    Existing DocTubeAI LangGraph
          |
          +--> STATUS
          |
          +--> TEXT
          |
          v
    VoicePipeline
          |
          +--> sentence buffering
          |
          +--> TTS


The important design principle is:

    VoiceAssistant does NOT create another assistant execution
    mechanism.

    It simply delegates to the existing VoiceGraphRunner.

This prevents duplicate:
    - generation counters
    - graph tasks
    - cancellation logic
    - timeout handling
    - graph lifecycle management
"""

# from __future__ import annotations

# import logging
# from typing import Optional

# from .graph_runner import VoiceGraphRunner
# from .models import (
#     VoiceGraphEvent,
#     VoiceGraphEventType,
# )

# logger = logging.getLogger(__name__)


# # ============================================================
# # Voice Assistant
# # ============================================================

# class VoiceAssistant:
#     """
#     Thin assistant-level facade over VoiceGraphRunner.

#     The actual streaming execution remains owned by
#     VoiceGraphRunner.

#     This class intentionally contains very little logic.

#     Why?

#     Because having both VoiceAssistant and VoiceGraphRunner
#     independently manage assistant execution would create
#     duplicated lifecycle management.

#     Current ownership:

#         VoicePipeline
#             |
#             +--> VoiceAssistant
#                     |
#                     +--> VoiceGraphRunner
#                             |
#                             +--> LangGraph

#     VoicePipeline remains responsible for consuming the
#     resulting STATUS and TEXT events.
#     """

#     def __init__(
#         self,
#         graph_runner: Optional[
#             VoiceGraphRunner
#         ] = None,
#     ) -> None:

#         # ----------------------------------------------------
#         # Reuse the existing graph runner.
#         #
#         # We do NOT construct another LangGraph.
#         # ----------------------------------------------------

#         self.graph_runner = (
#             graph_runner
#             or VoiceGraphRunner()
#         )

#         logger.debug(
#             "VoiceAssistant initialized."
#         )

#     # ========================================================
#     # Streaming execution
#     # ========================================================

#     async def stream(
#         self,
#         text: str,
#         session_id: str,
#     ):
#         """
#         Stream assistant events from the existing DocTubeAI
#         LangGraph.

#         The method simply delegates to VoiceGraphRunner.

#         The returned events are:

#             VoiceGraphEventType.STATUS

#                 Short progress information such as:

#                     "I'm checking your documents."

#                     "I'm checking the web for more information."

#             VoiceGraphEventType.TEXT

#                 Actual assistant answer tokens.

#         The assistant does NOT:
#             - modify the graph
#             - inspect graph nodes
#             - perform retrieval
#             - perform TTS
#             - buffer sentences
#             - send WebSocket messages
#         """

#         text = text.strip()

#         if not text:
#             return

#         if not session_id:
#             raise ValueError(
#                 "session_id must not be empty."
#             )

#         logger.info(
#             "🤖 Starting assistant stream "
#             "session=%s",
#             session_id,
#         )

#         try:

#             # ------------------------------------------------
#             # Delegate directly to the existing graph runner.
#             #
#             # This is the important part.
#             #
#             # There is only ONE LangGraph execution path.
#             # ------------------------------------------------

#             async for event in (
#                 self.graph_runner.stream(
#                     text,
#                     session_id,
#                 )
#             ):

#                 # --------------------------------------------
#                 # Only expose valid voice graph events.
#                 # --------------------------------------------

#                 if not isinstance(
#                     event,
#                     VoiceGraphEvent,
#                 ):

#                     logger.warning(
#                         "Ignoring unexpected assistant "
#                         "event type=%s session=%s",
#                         type(event).__name__,
#                         session_id,
#                     )

#                     continue

#                 # --------------------------------------------
#                 # STATUS
#                 #
#                 # Status events are generated by the
#                 # VoiceGraphRunner / VoiceStatusManager layer.
#                 #
#                 # They are NOT assistant answer text.
#                 # --------------------------------------------

#                 if (
#                     event.type
#                     == VoiceGraphEventType.STATUS
#                 ):

#                     if not event.content:
#                         continue

#                     yield event

#                     continue

#                 # --------------------------------------------
#                 # TEXT
#                 #
#                 # Text events contain actual assistant
#                 # response content.
#                 #
#                 # VoicePipeline will later:
#                 #
#                 #     token
#                 #       ↓
#                 #     sentence buffer
#                 #       ↓
#                 #     TTS
#                 # --------------------------------------------

#                 if (
#                     event.type
#                     == VoiceGraphEventType.TEXT
#                 ):

#                     if not event.content:
#                         continue

#                     yield event

#                     continue

#                 # --------------------------------------------
#                 # Unknown event types remain internal.
#                 # --------------------------------------------

#                 logger.debug(
#                     "Ignoring unsupported assistant "
#                     "event type=%s session=%s",
#                     event.type,
#                     session_id,
#                 )

#             logger.info(
#                 "✅ Assistant stream completed "
#                 "session=%s",
#                 session_id,
#             )

#         except Exception:

#             logger.exception(
#                 "❌ Assistant stream failed "
#                 "session=%s",
#                 session_id,
#             )

#             raise

#     # ========================================================
#     # Cancellation
#     # ========================================================

#     async def cancel(self) -> None:
#         """
#         Cancel the currently running assistant execution.

#         IMPORTANT:

#         VoiceGraphRunner owns the actual graph stream.

#         Therefore this class should NOT maintain its own
#         asyncio.Task or generation counter.

#         The VoicePipeline owns the task that consumes this
#         stream and cancellation propagates naturally through
#         the async generator.

#         This method exists only as a clean application-level
#         boundary for callers that want an assistant cancel
#         operation.
#         """

#         logger.info(
#             "🛑 Assistant cancellation requested."
#         )

#         # ----------------------------------------------------
#         # The graph runner itself currently exposes the stream
#         # as an async generator.
#         #
#         # There is no independent assistant task here to
#         # cancel.
#         #
#         # Cancellation is propagated by cancelling the task
#         # consuming graph_runner.stream().
#         # ----------------------------------------------------

#         return None

#     # ========================================================
#     # Close
#     # ========================================================

#     async def close(self) -> None:
#         """
#         Close the assistant boundary.

#         There are currently no assistant-owned resources.

#         LangGraph, HTTP clients, Postgres pools, TTS and other
#         resources are owned by their respective components.
#         """

#         logger.debug(
#             "🔌 VoiceAssistant closed."
#         )