"""
Shared data models for the voice pipeline.

This module contains only data structures.

It must not contain:
    - audio processing
    - VAD logic
    - Whisper logic
    - turn detection logic
    - LangGraph logic
    - TTS logic
    - WebSocket logic
"""

from dataclasses import dataclass
from enum import Enum
from typing import Literal, Optional


# ============================================================
# Audio
# ============================================================


class AudioActivity(str, Enum):
    UNKNOWN = "unknown"
    SILENCE = "silence"
    SPEECH = "speech"


@dataclass(slots=True)
class AudioActivityResult:
    """
    Result of audio activity / VAD analysis.
    """

    activity: AudioActivity

    probability: Optional[float] = None

    duration_seconds: Optional[float] = None


# ============================================================
# Transcription
# ============================================================


@dataclass(slots=True)
class TranscriptionResult:
    """
    Result returned by the transcription engine.

    This model intentionally does not know which
    transcription engine produced the result.
    """

    text: str

    language: Optional[str] = None

    language_probability: Optional[float] = None

    duration_seconds: Optional[float] = None

    has_speech: bool = False

    speech_probability: Optional[float] = None


# ============================================================
# User speech / turns
# ============================================================


@dataclass(slots=True)
class SpeechStarted:
    """
    Emitted when the system detects the beginning
    of a user's speech turn.
    """

    turn_id: int


@dataclass(slots=True)
class TranscriptChanged:
    """
    Emitted whenever the current user transcript changes.

    This is a partial / intermediate transcript.
    """

    turn_id: int

    text: str


@dataclass(slots=True)
class TurnCompleted:
    """
    Emitted when the user's speech turn is complete
    and the final transcript is available.
    """

    turn_id: int

    text: str


# ============================================================
# Interruption
# ============================================================


class InterruptionReason(str, Enum):
    USER_SPEECH = "user_speech"
    USER_CANCEL = "user_cancel"
    SESSION_CLOSED = "session_closed"
    TIMEOUT = "timeout"


@dataclass(slots=True)
class AssistantInterrupted:
    """
    Represents cancellation/interruption of the
    currently running assistant turn.
    """

    turn_id: int

    reason: InterruptionReason


# ============================================================
# Assistant
# ============================================================


@dataclass(slots=True)
class AssistantRequest:
    """
    Request sent from the voice pipeline to the
    assistant layer.
    """

    text: str

    session_id: str

    turn_id: int


@dataclass(slots=True)
class AssistantResponse:
    """
    Final response produced by the assistant layer.
    """

    text: str

    turn_id: int


# ============================================================
# Assistant lifecycle
# ============================================================


@dataclass(slots=True)
class AssistantStarted:
    """
    Assistant processing has started for a user turn.
    """

    turn_id: int


@dataclass(slots=True)
class AssistantCompleted:
    """
    Assistant processing has completed successfully.
    """

    turn_id: int


@dataclass(slots=True)
class AssistantError:
    """
    Assistant processing failed.

    turn_id may be None if the failure happened before
    a valid assistant turn was established.
    """

    turn_id: Optional[int]

    error: str


# ============================================================
# Voice graph stream
# ============================================================


class VoiceGraphEventType(str, Enum):
    """
    Type of event produced by the voice-specific
    LangGraph streaming adapter.
    """

    STATUS = "status"
    TEXT = "text"


@dataclass(slots=True)
class VoiceGraphEvent:
    """
    Event emitted by VoiceGraphRunner while executing
    the LangGraph workflow.

    STATUS events represent meaningful conversational
    progress such as:

        "I'm searching your documents."

    TEXT events represent actual assistant answer
    content that should eventually be sent to TTS.

    Keeping these two types separate is important because
    status messages must never enter the normal answer
    sentence buffer.
    """

    type: VoiceGraphEventType

    content: str


# ============================================================
# Playback
# ============================================================


@dataclass(slots=True)
class PlaybackStarted:
    """
    TTS/audio playback has started.
    """

    turn_id: int


@dataclass(slots=True)
class PlaybackStopped:
    """
    TTS/audio playback has completed or stopped normally.
    """

    turn_id: int


@dataclass(slots=True)
class PlaybackInterrupted:
    """
    TTS/audio playback was interrupted.
    """

    turn_id: int

    reason: InterruptionReason


# ============================================================
# Pipeline lifecycle
# ============================================================


class VoicePipelineStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    CLOSING = "closing"
    CLOSED = "closed"


@dataclass(slots=True)
class VoicePipelineState:
    """
    Runtime state owned by VoicePipeline.

    This is state only. It contains no processing logic.
    """

    session_id: str

    status: VoicePipelineStatus = (
        VoicePipelineStatus.CREATED
    )

    # --------------------------------------------------------
    # User turn
    # --------------------------------------------------------

    turn_id: int = 0

    user_speaking: bool = False

    # --------------------------------------------------------
    # Assistant
    # --------------------------------------------------------

    assistant_turn_id: Optional[int] = None

    assistant_processing: bool = False

    assistant_playing: bool = False

    # --------------------------------------------------------
    # Interruption
    # --------------------------------------------------------

    interrupted: bool = False