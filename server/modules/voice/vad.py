"""
Voice Activity Detection.

File:
    voice/vad.py

Responsibilities:
    - Detect speech activity from PCM16 audio.
    - Ignore silence cheaply.
    - Keep a small amount of audio before confirmed speech.
    - Keep a small amount of trailing silence after speech.
    - Confirm speech only after the minimum duration.
    - Emit SPEECH_STARTED when speech is confirmed.
    - Emit SPEECH_ENDED with the complete speech segment.

This module does NOT know about:
    - Whisper
    - WebSockets
    - LangGraph
    - TTS
    - assistants
    - conversational turns
    - frontend events

Architecture:

    PCM16 frame
        ↓
    energy gate
        ↓
    ┌──────────────────────┐
    │                      │
    │  SILENT / CANDIDATE  │
    │                      │
    └──────────┬───────────┘
               │
        enough speech
               ↓
    ┌──────────────────────┐
    │                      │
    │       SPEAKING       │
    │                      │
    └──────────┬───────────┘
               │
        enough silence
               ↓
         SPEECH_ENDED
               ↓
             reset
"""


from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .config import (
    VAD_ENERGY_THRESHOLD,
    VAD_MIN_SPEECH_SECONDS,
    VAD_POST_SPEECH_SECONDS,
    VAD_PRE_SPEECH_SECONDS,
    VAD_SILENCE_SECONDS,
)


logger = logging.getLogger(__name__)


# ============================================================
# Events
# ============================================================


class VADEventType(str, Enum):
    """
    Lifecycle events emitted by the VAD.
    """

    SPEECH_STARTED = "speech_started"
    SPEECH_ENDED = "speech_ended"


@dataclass(slots=True)
class VADEvent:
    """
    Event emitted by VoiceActivityDetector.

    SPEECH_STARTED:
        Speech has been confirmed.

        audio is empty because the speech segment is not
        complete yet.

    SPEECH_ENDED:
        Speech has ended.

        audio contains the complete PCM16 segment including:
            - pre-speech context
            - confirmed speech
            - trailing silence
    """

    type: VADEventType

    speech_duration: float

    audio: bytes = b""


# ============================================================
# Runtime state
# ============================================================


@dataclass(slots=True)
class VADState:
    """
    Runtime state of the detector.

    speaking:
        True only after candidate speech has reached
        min_speech_seconds.

    candidate_duration:
        Duration of speech seen before confirmation.

    speech_duration:
        Duration of confirmed speech.

    silence_duration:
        Duration of silence after confirmed speech.
    """

    speaking: bool = False

    speech_started_at: Optional[float] = None

    last_speech_at: Optional[float] = None

    speech_duration: float = 0.0

    silence_duration: float = 0.0

    candidate_duration: float = 0.0


# ============================================================
# Detector
# ============================================================


class VoiceActivityDetector:
    """
    Energy-based voice activity detector.

    Input:

        PCM16 mono audio frames.

    Output:

        SPEECH_STARTED
            ↓
        user continues speaking
            ↓
        SPEECH_ENDED + complete PCM16 audio

    Important:

        This class only determines speech lifecycle.

        It does NOT decide whether the resulting speech
        represents a conversational turn.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 20,
        energy_threshold: float = VAD_ENERGY_THRESHOLD,
        min_speech_seconds: float = VAD_MIN_SPEECH_SECONDS,
        silence_seconds: float = VAD_SILENCE_SECONDS,
        pre_speech_seconds: float = VAD_PRE_SPEECH_SECONDS,
        post_speech_seconds: float = VAD_POST_SPEECH_SECONDS,
    ) -> None:

        # ----------------------------------------------------
        # Validate configuration once during construction.
        # ----------------------------------------------------

        if sample_rate <= 0:
            raise ValueError(
                "sample_rate must be greater than zero."
            )

        if frame_duration_ms <= 0:
            raise ValueError(
                "frame_duration_ms must be greater than zero."
            )

        if energy_threshold < 0:
            raise ValueError(
                "energy_threshold cannot be negative."
            )

        if min_speech_seconds < 0:
            raise ValueError(
                "min_speech_seconds cannot be negative."
            )

        if silence_seconds <= 0:
            raise ValueError(
                "silence_seconds must be greater than zero."
            )

        if pre_speech_seconds < 0:
            raise ValueError(
                "pre_speech_seconds cannot be negative."
            )

        if post_speech_seconds < 0:
            raise ValueError(
                "post_speech_seconds cannot be negative."
            )

        self.sample_rate = sample_rate
        self.frame_duration_ms = frame_duration_ms

        self.energy_threshold = energy_threshold
        self.min_speech_seconds = min_speech_seconds
        self.silence_seconds = silence_seconds

        self.pre_speech_seconds = pre_speech_seconds
        self.post_speech_seconds = post_speech_seconds

        self.state = VADState()

        # ----------------------------------------------------
        # Audio immediately before speech is confirmed.
        #
        # Example:
        #
        #       silence | "hello"
        #               ↑
        #        confirmation happens here
        #
        # The pre-speech audio is retained so Whisper does
        # not lose the beginning of the utterance.
        # ----------------------------------------------------

        self._pre_speech_frames: deque[bytes] = deque()
        self._pre_speech_duration = 0.0

        # ----------------------------------------------------
        # Trailing silence after speech.
        #
        # We wait for enough silence before declaring the
        # utterance complete.
        #
        # Keeping the trailing audio helps preserve natural
        # boundaries for transcription.
        # ----------------------------------------------------

        self._post_speech_frames: deque[bytes] = deque()
        self._post_speech_duration = 0.0

        # ----------------------------------------------------
        # Complete audio belonging to the current utterance.
        #
        # This contains:
        #
        #     pre-speech + speech + trailing silence
        # ----------------------------------------------------

        self._speech_frames: list[bytes] = []

        # ----------------------------------------------------
        # Logical audio clock.
        #
        # We advance this using the actual duration of the
        # PCM frame rather than wall-clock time.
        #
        # Therefore VAD behaviour does not depend on whether
        # the CPU processes audio faster or slower than realtime.
        # ----------------------------------------------------

        self._current_time = 0.0

    # ========================================================
    # Properties
    # ========================================================

    @property
    def speaking(self) -> bool:
        """
        True after speech has been confirmed.
        """

        return self.state.speaking

    @property
    def speech_duration(self) -> float:
        """
        Duration of confirmed voiced audio.

        This intentionally does not include:
            - pre-speech context
            - trailing silence
        """

        return self.state.speech_duration

    @property
    def current_time(self) -> float:
        """
        Logical amount of PCM audio processed since reset().
        """

        return self._current_time

    # ========================================================
    # Process frame
    # ========================================================

    def process(
        self,
        audio_frame: bytes,
    ) -> list[VADEvent]:
        """
        Process one PCM16 audio frame.

        Returns:
            Zero or more VAD lifecycle events.

        Expected input:
            PCM16 mono audio.
        """

        if not audio_frame:
            return []

        # ----------------------------------------------------
        # PCM16 contains 2 bytes per sample.
        #
        # A single byte cannot form a complete sample.
        # ----------------------------------------------------

        if len(audio_frame) < 2:
            return []

        # ----------------------------------------------------
        # Ignore a trailing incomplete sample.
        #
        # This protects the energy calculation from malformed
        # input without raising an exception.
        # ----------------------------------------------------

        if len(audio_frame) % 2:
            audio_frame = audio_frame[:-1]

        if not audio_frame:
            return []

        frame_samples = len(audio_frame) // 2

        # ----------------------------------------------------
        # Derive duration from the actual PCM payload.
        #
        # This is safer than blindly trusting
        # frame_duration_ms because decoded frames can
        # theoretically have different sizes.
        # ----------------------------------------------------

        frame_duration = (
            frame_samples / self.sample_rate
        )

        self._current_time += frame_duration

        is_speech = self._is_speech(audio_frame)

        # ----------------------------------------------------
        # Once speech is confirmed, use the speaking state
        # machine.
        # ----------------------------------------------------

        if self.state.speaking:

            return self._process_while_speaking(
                audio_frame=audio_frame,
                frame_duration=frame_duration,
                is_speech=is_speech,
            )

        # ----------------------------------------------------
        # Otherwise we are either silent or accumulating
        # candidate speech.
        # ----------------------------------------------------

        return self._process_while_silent(
            audio_frame=audio_frame,
            frame_duration=frame_duration,
            is_speech=is_speech,
        )

    # ========================================================
    # Silent / candidate state
    # ========================================================

    def _process_while_silent(
        self,
        audio_frame: bytes,
        frame_duration: float,
        is_speech: bool,
    ) -> list[VADEvent]:

        # ----------------------------------------------------
        # Silence means there is no current speech candidate.
        #
        # Keep this frame as possible pre-speech context.
        # ----------------------------------------------------

        if not is_speech:

            self.state.candidate_duration = 0.0

            self._speech_frames.clear()

            self._add_pre_speech_frame(
                audio_frame,
                frame_duration,
            )

            return []

        # ----------------------------------------------------
        # We have detected possible speech.
        #
        # Do not immediately declare SPEECH_STARTED.
        #
        # A short noise burst should not become a speech turn.
        # ----------------------------------------------------

        self._speech_frames.append(audio_frame)

        self.state.candidate_duration += frame_duration

        # ----------------------------------------------------
        # Not enough continuous speech yet.
        # ----------------------------------------------------

        if (
            self.state.candidate_duration
            < self.min_speech_seconds
        ):
            return []

        # ----------------------------------------------------
        # Speech is now confirmed.
        # ----------------------------------------------------

        self.state.speaking = True

        self.state.speech_started_at = (
            self._current_time
            - self.state.candidate_duration
        )

        self.state.last_speech_at = (
            self._current_time
        )

        self.state.speech_duration = (
            self.state.candidate_duration
        )

        self.state.silence_duration = 0.0

        # ----------------------------------------------------
        # The speech segment begins slightly before the VAD
        # confirmation point.
        #
        # Add the pre-speech buffer so the beginning of a
        # spoken word is not lost.
        # ----------------------------------------------------

        self._speech_frames = (
            list(self._pre_speech_frames)
            + self._speech_frames
        )

        self._clear_pre_speech_buffer()
        self._clear_post_speech_buffer()

        self.state.candidate_duration = 0.0

        logger.info(
            "🗣 VAD speech started duration=%.2f",
            self.state.speech_duration,
        )

        # ----------------------------------------------------
        # Do not emit audio here.
        #
        # The audio segment is incomplete until speech ends.
        # ----------------------------------------------------

        return [
            VADEvent(
                type=VADEventType.SPEECH_STARTED,
                speech_duration=self.state.speech_duration,
            )
        ]

    # ========================================================
    # Confirmed speaking state
    # ========================================================

    def _process_while_speaking(
        self,
        audio_frame: bytes,
        frame_duration: float,
        is_speech: bool,
    ) -> list[VADEvent]:

        # ----------------------------------------------------
        # User is still speaking.
        # ----------------------------------------------------

        if is_speech:

            self.state.last_speech_at = (
                self._current_time
            )

            self.state.speech_duration += (
                frame_duration
            )

            self.state.silence_duration = 0.0

            self._speech_frames.append(
                audio_frame
            )

            # Any previous trailing silence is no longer
            # trailing silence because speech resumed.
            self._clear_post_speech_buffer()

            return []

        # ----------------------------------------------------
        # Confirmed speech followed by silence.
        #
        # Do not immediately end the utterance.
        #
        # Short pauses between words should remain inside the
        # same speech segment.
        # ----------------------------------------------------

        self.state.silence_duration += frame_duration

        self._post_speech_frames.append(
            audio_frame
        )

        self._post_speech_duration += frame_duration

        self._trim_post_speech_buffer()

        # ----------------------------------------------------
        # Not enough silence yet.
        # ----------------------------------------------------

        if (
            self.state.silence_duration
            < self.silence_seconds
        ):
            return []

        # ----------------------------------------------------
        # Enough silence has accumulated.
        #
        # The utterance is complete.
        # ----------------------------------------------------

        speech_duration = self.state.speech_duration

        self._speech_frames.extend(
            self._post_speech_frames
        )

        speech_audio = b"".join(
            self._speech_frames
        )

        logger.info(
            "🛑 VAD speech ended "
            "duration=%.2f audio=%d bytes",
            speech_duration,
            len(speech_audio),
        )

        event = VADEvent(
            type=VADEventType.SPEECH_ENDED,
            speech_duration=speech_duration,
            audio=speech_audio,
        )

        # ----------------------------------------------------
        # A completed segment must not remain in the detector.
        #
        # Reset prepares the VAD for the next utterance.
        # ----------------------------------------------------

        self.reset()

        return [event]

    # ========================================================
    # Energy gate
    # ========================================================

    def _is_speech(
        self,
        audio_frame: bytes,
    ) -> bool:
        """
        Determine whether a PCM16 frame contains enough
        energy to be considered speech.

        This is an energy gate, not a real speech classifier.

        Therefore:
            loud background noise can trigger it
            quiet speech can fail it

        The configured threshold determines that trade-off.
        """

        sample_count = len(audio_frame) // 2

        if sample_count <= 0:
            return False

        total_squared = 0.0

        # ----------------------------------------------------
        # PCM16 is little-endian signed int16.
        #
        # Convert each sample to [-1.0, 1.0] and calculate
        # RMS energy.
        # ----------------------------------------------------

        for index in range(0, len(audio_frame), 2):

            sample = int.from_bytes(
                audio_frame[index:index + 2],
                byteorder="little",
                signed=True,
            )

            normalized = sample / 32768.0

            total_squared += normalized * normalized

        rms = math.sqrt(
            total_squared / sample_count
        )

        return rms >= self.energy_threshold

    # ========================================================
    # Pre-speech buffer
    # ========================================================

    def _add_pre_speech_frame(
        self,
        audio_frame: bytes,
        frame_duration: float,
    ) -> None:
        """
        Keep recent audio before speech confirmation.

        This prevents VAD confirmation latency from cutting
        off the beginning of the user's utterance.
        """

        if self.pre_speech_seconds <= 0:
            return

        self._pre_speech_frames.append(
            audio_frame
        )

        self._pre_speech_duration += frame_duration

        while (
            self._pre_speech_duration
            > self.pre_speech_seconds
            and self._pre_speech_frames
        ):

            removed = (
                self._pre_speech_frames.popleft()
            )

            self._pre_speech_duration -= (
                self._frame_duration(removed)
            )

    def _clear_pre_speech_buffer(self) -> None:

        self._pre_speech_frames.clear()

        self._pre_speech_duration = 0.0

    # ========================================================
    # Post-speech buffer
    # ========================================================

    def _trim_post_speech_buffer(self) -> None:
        """
        Keep only the configured amount of trailing silence.
        """

        if self.post_speech_seconds <= 0:

            self._clear_post_speech_buffer()

            return

        while (
            self._post_speech_duration
            > self.post_speech_seconds
            and self._post_speech_frames
        ):

            removed = (
                self._post_speech_frames.popleft()
            )

            self._post_speech_duration -= (
                self._frame_duration(removed)
            )

    def _clear_post_speech_buffer(self) -> None:

        self._post_speech_frames.clear()

        self._post_speech_duration = 0.0

    # ========================================================
    # Frame duration
    # ========================================================

    def _frame_duration(
        self,
        audio_frame: bytes,
    ) -> float:
        """
        Calculate PCM16 frame duration from its byte length.
        """

        return (
            (len(audio_frame) // 2)
            / self.sample_rate
        )

    # ========================================================
    # Reset
    # ========================================================

    def reset(self) -> None:
        """
        Completely reset the VAD lifecycle.

        This means:

            no active speech
            no candidate speech
            no buffered speech
            no pre-speech audio
            no post-speech audio
            logical clock starts again at zero
        """

        self.state = VADState()

        self._speech_frames.clear()

        self._clear_pre_speech_buffer()

        self._clear_post_speech_buffer()

        self._current_time = 0.0


# ============================================================
# Factory
# ============================================================


def create_vad(
    sample_rate: int = 16000,
    frame_duration_ms: int = 20,
) -> VoiceActivityDetector:
    """
    Create the application's configured VAD.

    Keeping configuration in the factory means callers do not
    need to know the individual VAD configuration values.
    """

    return VoiceActivityDetector(
        sample_rate=sample_rate,
        frame_duration_ms=frame_duration_ms,
        energy_threshold=VAD_ENERGY_THRESHOLD,
        min_speech_seconds=VAD_MIN_SPEECH_SECONDS,
        silence_seconds=VAD_SILENCE_SECONDS,
        pre_speech_seconds=VAD_PRE_SPEECH_SECONDS,
        post_speech_seconds=VAD_POST_SPEECH_SECONDS,
    )