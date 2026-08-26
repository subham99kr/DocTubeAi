"""
Voice turn detection.

File:
    voice/turn_detector.py

Responsibilities:
    - Convert VAD speech lifecycle events into conversational events.
    - Associate a completed transcript with the active speech turn.
    - Emit SpeechStarted.
    - Emit TranscriptChanged.
    - Emit TurnCompleted after speech has ended and a transcript exists.
    - Prevent empty transcripts from reaching the assistant.
    - Keep conversational state isolated from audio, Whisper, TTS
      and LangGraph.

Important lifecycle:

    VAD SPEECH_STARTED
        ↓
    TurnDetector starts a turn
        ↓
    Whisper produces transcript
        ↓
    process_transcript()
        ↓
    TranscriptChanged
        ↓
    VAD SPEECH_ENDED
        ↓
    process_vad_event()
        ↓
    TurnCompleted

This module does NOT:
    - inspect audio
    - perform VAD
    - run Whisper
    - call LangGraph
    - perform TTS
    - manage WebSockets
    - manage frontend state

NOTE:

    The current pipeline starts transcription asynchronously after
    SPEECH_ENDED. Therefore this detector intentionally keeps the
    turn active until the pipeline sends the corresponding
    SPEECH_ENDED event after transcription has completed.

    This preserves the existing public interface but means that
    very rapid consecutive speech segments require coordination
    at the pipeline layer.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import List, Union

from .models import (
    SpeechStarted,
    TranscriptChanged,
    TurnCompleted,
)
from .vad import VADEvent, VADEventType


logger = logging.getLogger(__name__)


# ============================================================
# Types
# ============================================================

TurnEvent = Union[
    SpeechStarted,
    TranscriptChanged,
    TurnCompleted,
]


# ============================================================
# Turn state
# ============================================================


@dataclass(slots=True)
class TurnState:
    """
    Mutable state belonging to the current conversational turn.

    turn_id:
        Monotonically increasing identifier for each user turn.

    active:
        True while the detector considers the current speech
        segment to belong to an open conversational turn.

    transcript:
        Latest usable transcript associated with this turn.
    """

    turn_id: int = 0
    active: bool = False
    transcript: str = ""


# ============================================================
# Turn detector
# ============================================================


class TurnDetector:
    """
    Converts VAD and transcription events into conversational events.

    Responsibilities are deliberately narrow:

        VAD
          ↓
        speech lifecycle
          ↓
        TurnDetector
          ↓
        conversational events

    VAD answers:

        "Is the user speaking?"

    TurnDetector answers:

        "What conversational turn does this speech belong to?"
    """

    def __init__(self) -> None:

        self.state = TurnState()

        # ----------------------------------------------------
        # Multiple async callers can potentially reach the
        # detector through the pipeline.
        #
        # All state transitions therefore happen under one
        # lock.
        # ----------------------------------------------------

        self._lock = asyncio.Lock()

    # ========================================================
    # VAD events
    # ========================================================

    async def process_vad_event(
        self,
        event: VADEvent,
    ) -> List[TurnEvent]:
        """
        Process a VAD lifecycle event.

        SPEECH_STARTED:
            Opens a new conversational turn.

        SPEECH_ENDED:
            Closes the current turn only when the pipeline has
            already supplied a usable transcript.

        Other VAD events are ignored.
        """

        async with self._lock:

            if (
                event.type
                == VADEventType.SPEECH_STARTED
            ):

                return self._handle_speech_started()

            if (
                event.type
                == VADEventType.SPEECH_ENDED
            ):

                return self._handle_speech_ended()

            return []

    # ========================================================
    # Speech started
    # ========================================================

    def _handle_speech_started(
        self,
    ) -> List[TurnEvent]:
        """
        Start a new conversational turn.

        Duplicate SPEECH_STARTED events are ignored while a
        turn is already active.
        """

        if self.state.active:

            logger.debug(
                "Ignoring duplicate speech start "
                "turn=%s",
                self.state.turn_id,
            )

            return []

        # ----------------------------------------------------
        # Allocate the next turn ID.
        # ----------------------------------------------------

        self.state.turn_id += 1

        self.state.active = True

        self.state.transcript = ""

        turn_id = self.state.turn_id

        logger.info(
            "Speech started "
            "turn=%s",
            turn_id,
        )

        return [
            SpeechStarted(
                turn_id=turn_id,
            )
        ]

    # ========================================================
    # Transcript
    # ========================================================

    async def process_transcript(
        self,
        transcript: str,
    ) -> List[TurnEvent]:
        """
        Associate a transcript with the active turn.

        A transcript cannot create a turn by itself.

        VAD must have opened the turn first.
        """

        transcript = transcript.strip()

        if not transcript:
            return []

        async with self._lock:

            # ------------------------------------------------
            # Whisper output without an active speech turn
            # cannot safely be associated with a conversation.
            # ------------------------------------------------

            if not self.state.active:

                logger.debug(
                    "Ignoring transcript without "
                    "active turn: %r",
                    transcript,
                )

                return []

            # ------------------------------------------------
            # Ignore identical transcription results.
            #
            # This protects the frontend from receiving the
            # same transcript repeatedly.
            # ------------------------------------------------

            if (
                transcript
                == self.state.transcript
            ):

                return []

            self.state.transcript = transcript

            turn_id = self.state.turn_id

            logger.debug(
                "Transcript changed "
                "turn=%s text=%r",
                turn_id,
                transcript,
            )

            return [
                TranscriptChanged(
                    turn_id=turn_id,
                    text=transcript,
                )
            ]

    # ========================================================
    # Speech ended
    # ========================================================

    def _handle_speech_ended(
        self,
    ) -> List[TurnEvent]:
        """
        Close the current conversational turn.

        The important rule is:

            speech ended + transcript
                → TurnCompleted

            speech ended + no transcript
                → discard the turn

        This prevents empty/noise VAD segments from reaching
        the assistant.
        """

        if not self.state.active:

            logger.debug(
                "Ignoring speech end without "
                "an active turn."
            )

            return []

        turn_id = self.state.turn_id

        final_text = self.state.transcript.strip()

        # ----------------------------------------------------
        # The speech lifecycle is now closed.
        #
        # Marking the turn inactive happens before returning
        # so the detector cannot accidentally reuse it.
        # ----------------------------------------------------

        self.state.active = False

        # ----------------------------------------------------
        # No transcript means there is nothing useful to send
        # to the assistant.
        # ----------------------------------------------------

        if not final_text:

            logger.debug(
                "Dropping empty turn "
                "turn=%s",
                turn_id,
            )

            self.state.transcript = ""

            return []

        # ----------------------------------------------------
        # Create the immutable completion event before clearing
        # internal state.
        # ----------------------------------------------------

        completed = TurnCompleted(
            turn_id=turn_id,
            text=final_text,
        )

        logger.info(
            "Turn completed "
            "turn=%s text=%r",
            turn_id,
            final_text,
        )

        # ----------------------------------------------------
        # The detector is now ready for the next turn.
        # ----------------------------------------------------

        self.state.transcript = ""

        return [
            completed
        ]

    # ========================================================
    # State
    # ========================================================

    @property
    def active(self) -> bool:
        """
        Whether a conversational turn is currently active.
        """

        return self.state.active

    @property
    def turn_id(self) -> int:
        """
        ID of the current/latest conversational turn.
        """

        return self.state.turn_id

    @property
    def current_transcript(self) -> str:
        """
        Latest transcript stored for the active turn.
        """

        return self.state.transcript

    # ========================================================
    # Reset
    # ========================================================

    async def reset(self) -> None:
        """
        Completely reset conversational state.

        Used when:
            - the voice session closes
            - the session is aborted
            - the pipeline is restarted
        """

        async with self._lock:

            self.state = TurnState()

        logger.debug(
            "Turn detector reset."
        )