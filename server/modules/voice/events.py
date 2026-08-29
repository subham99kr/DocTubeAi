"""
Voice WebSocket event protocol.

This module is responsible ONLY for creating the dictionaries
that are sent from the server to the frontend over WebSocket.

It does NOT:

    - execute LangGraph
    - inspect LangGraph nodes
    - decide assistant status messages
    - perform TTS
    - perform STT
    - manage conversation state
    - manage assistant execution
    - manage interruptions

Architecture:

    LangGraph
        ↓
    VoiceGraphRunner
        ↓
    VoiceGraphEvent
        ↓
    VoicePipeline
        ↓
    events.py
        ↓
    WebSocket
        ↓
    Frontend

The event functions in this file should remain simple and
predictable. They convert internal pipeline callbacks into
stable frontend-facing event payloads.
"""

from __future__ import annotations

import base64
from typing import Any, Optional

# ============================================================
# Generic event builder
# ============================================================


def event(
    event_type: str,
    **payload: Any,
) -> dict:
    """
    Create a generic WebSocket event.

    Every server → client event has the same top-level shape:

        {
            "type": "...",
            ...
        }

    Example:

        event(
            "assistant_text",
            text="Hello",
            turn_id=1,
        )

    becomes:

        {
            "type": "assistant_text",
            "text": "Hello",
            "turn_id": 1,
        }

    This function intentionally contains no business logic.
    """

    return {
        "type": event_type,
        **payload,
    }


# ============================================================
# Connection / session
# ============================================================


def connected() -> dict:
    """
    Notify the frontend that the WebSocket connection
    has been established.
    """

    return event(
        "connected",
    )


def session_started() -> dict:
    """
    Notify the frontend that the voice session has started.
    """

    return event(
        "session_started",
    )


def session_ended() -> dict:
    """
    Notify the frontend that the voice session has ended.
    """

    return event(
        "session_ended",
    )


# ============================================================
# User speech
# ============================================================


def user_speech_started(
    turn_id: int,
) -> dict:
    """
    Notify the frontend that the user has started speaking.

    This is generated from the voice pipeline's speech/VAD
    and turn-detection layer.

    It does NOT contain the transcript.
    """

    return event(
        "user_speech_started",
        turn_id=turn_id,
    )


def transcript_partial(
    text: str,
    turn_id: int,
) -> dict:
    """
    Send an intermediate transcript to the frontend.

    This is useful for displaying what Whisper/turn detection
    currently believes the user is saying.

    This is NOT necessarily the final user query.
    """

    return event(
        "transcript_partial",
        text=text,
        turn_id=turn_id,
    )


def transcript_final(
    text: str,
    turn_id: int,
) -> dict:
    """
    Send the finalized transcription for the current
    user speech segment.

    This represents the confirmed transcript rather than
    an intermediate transcription update.
    """

    return event(
        "transcript_final",
        text=text,
        turn_id=turn_id,
    )


def user_turn_complete(
    text: str,
    turn_id: int,
) -> dict:
    """
    Notify the frontend that the complete user turn has
    been identified.

    At this point the voice pipeline can start the assistant
    execution.
    """

    return event(
        "user_turn_complete",
        text=text,
        turn_id=turn_id,
    )


# ============================================================
# Assistant lifecycle
# ============================================================


def assistant_started(
    turn_id: int,
) -> dict:
    """
    Notify the frontend that assistant processing has started.

    This happens before LangGraph answer streaming begins.
    """

    return event(
        "assistant_started",
        turn_id=turn_id,
    )


def assistant_status(
    message: str,
    turn_id: int,
) -> dict:
    """
    Send a short assistant progress message.

    Examples:

        "I'm checking your documents."

        "I'm checking the web for more information."

        "I'm narrowing down the most relevant information."

    Important:

    This is NOT part of the final assistant answer.

    The message originates from the graph execution/status
    layer and is simply serialized here for the frontend.

    This function does not decide what the status should be.
    """

    return event(
        "assistant_status",
        message=message.strip(),
        turn_id=turn_id,
    )


def assistant_text(
    text: str,
    turn_id: int,
) -> dict:
    """
    Send a chunk of the actual assistant answer.

    These chunks originate from the final conversational
    LangGraph nodes such as:

        simple_chat
        rag_chatbot

    They are separate from assistant_status events.

    The frontend can concatenate these chunks to display
    the streaming assistant response.
    """

    return event(
        "assistant_text",
        text=text,
        turn_id=turn_id,
    )


def assistant_audio(
    audio: bytes,
    turn_id: int,
    mime_type: str = "audio/mpeg",
) -> dict:
    """
    Send synthesized assistant audio to the frontend.

    WebSocket JSON messages cannot contain raw bytes.

    Therefore:

        bytes
            ↓
        base64
            ↓
        JSON string
            ↓
        WebSocket
            ↓
        frontend decodes base64
            ↓
        audio playback

    Args:
        audio:
            Raw synthesized audio bytes.

        turn_id:
            Assistant turn that produced the audio.

        mime_type:
            Audio MIME type expected by the frontend.
    """

    if not audio:
        return event(
            "assistant_audio",
            data="",
            turn_id=turn_id,
            mime_type=mime_type,
        )

    encoded_audio = base64.b64encode(audio).decode("ascii")

    return event(
        "assistant_audio",
        data=encoded_audio,
        turn_id=turn_id,
        mime_type=mime_type,
    )


def assistant_completed(
    turn_id: int,
) -> dict:
    """
    Notify the frontend that the assistant turn has
    completely finished.

    At this point:

        graph streaming
            ↓
        answer text
            ↓
        sentence synthesis
            ↓
        assistant execution

    has completed successfully.
    """

    return event(
        "assistant_completed",
        turn_id=turn_id,
    )


def assistant_error(
    turn_id: Optional[int],
    message: str,
) -> dict:
    """
    Notify the frontend that assistant execution failed.

    turn_id can be None if the error occurred before an
    assistant turn was established.
    """

    return event(
        "assistant_error",
        turn_id=turn_id,
        message=message,
    )


# ============================================================
# Interruption
# ============================================================


def interrupted(
    turn_id: int,
) -> dict:
    """
    Notify the frontend that the current assistant response
    was interrupted by the user.

    Typical flow:

        Assistant speaking
              ↓
        User starts speaking
              ↓
        VAD detects speech
              ↓
        Pipeline interrupts assistant
              ↓
        interrupted event
    """

    return event(
        "interrupted",
        turn_id=turn_id,
    )


# ============================================================
# General error
# ============================================================


def error(
    message: str,
    code: Optional[str] = None,
) -> dict:
    """
    Send a general WebSocket-level error.

    This is different from assistant_error():

        error()
            → connection/session/protocol-level problem

        assistant_error()
            → assistant execution problem
    """

    payload = {
        "message": message,
    }

    if code is not None:
        payload["code"] = code

    return event(
        "error",
        **payload,
    )


# ============================================================
# Server information
# ============================================================


def server_info(
    message: str,
) -> dict:
    """
    Send informational server messages to the frontend.

    This is intended for non-error informational messages
    that do not belong to the assistant answer stream.
    """

    return event(
        "server_info",
        message=message,
    )
