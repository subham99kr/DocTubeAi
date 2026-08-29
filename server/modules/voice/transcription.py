"""
Faster-Whisper transcription service.

Responsibilities:
    - Own the shared Faster-Whisper model.
    - Run blocking inference outside asyncio.
    - Apply Whisper's internal VAD as a secondary safeguard.
    - Convert Whisper output into TranscriptionResult.
    - Normalize and bound transcript output.
    - Provide an async lifecycle suitable for the voice pipeline.

This module does NOT know about:
    - WebSockets
    - microphone state
    - audio buffering
    - VAD state
    - turn detection
    - assistant state
    - interruption
    - LangGraph
    - TTS
    - frontend events
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import wave
from typing import Optional

from faster_whisper import WhisperModel

from modules.voice.config import (
    MAX_TRANSCRIPT_LENGTH,
    WHISPER_COMPUTE_TYPE,
    WHISPER_DEVICE,
    WHISPER_LANGUAGE,
    WHISPER_MODEL,
)
from modules.voice.models import TranscriptionResult

logger = logging.getLogger(__name__)


# ============================================================
# SHARED WHISPER MODEL
# ============================================================

# One Whisper model per Python process.
#
# Multiple voice sessions/transcribers will share this model.
_whisper_model: Optional[WhisperModel] = None

# Prevent multiple sessions from loading the model
# simultaneously when they start at the same time.
_whisper_model_lock = asyncio.Lock()


async def get_whisper_model() -> WhisperModel:
    """
    Return the shared Faster-Whisper model.

    The model is loaded only once per Python process.
    """

    global _whisper_model

    # Fast path:
    # Model has already been loaded.
    if _whisper_model is not None:
        return _whisper_model

    # Only one coroutine can initialize the model.
    async with _whisper_model_lock:
        # Double-check after acquiring the lock.
        #
        # Another coroutine may have loaded the model
        # while this coroutine was waiting for the lock.
        if _whisper_model is not None:
            return _whisper_model

        logger.info(
            "Loading Faster-Whisper model model=%s device=%s compute_type=%s",
            WHISPER_MODEL,
            WHISPER_DEVICE,
            WHISPER_COMPUTE_TYPE,
        )

        _whisper_model = await asyncio.to_thread(
            WhisperModel,
            WHISPER_MODEL,
            device=WHISPER_DEVICE,
            compute_type=WHISPER_COMPUTE_TYPE,
        )

        logger.info("Faster-Whisper model loaded.")

        return _whisper_model


class WhisperTranscriber:
    """
    Async lifecycle wrapper around Faster-Whisper.

    Each voice session gets its own WhisperTranscriber,
    but all transcribers share the same WhisperModel.

    Blocking inference is always executed outside the
    asyncio event loop.
    """

    def __init__(
        self,
        model: Optional[WhisperModel] = None,
    ) -> None:

        self.model = model

        self._started = False
        self._closed = False

        self._lock = asyncio.Lock()

    # ========================================================
    # Properties
    # ========================================================

    @property
    def started(self) -> bool:
        return self._started

    @property
    def closed(self) -> bool:
        return self._closed

    # ========================================================
    # Start
    # ========================================================

    async def start(self) -> None:
        """
        Initialize this transcriber.

        The underlying WhisperModel is shared globally.

        Calling start() multiple times is safe.
        """

        async with self._lock:
            if self._closed:
                raise RuntimeError("Cannot start a closed transcriber.")

            if self._started:
                return

            # Get the shared Whisper model.
            #
            # This loads the model only if it has not
            # already been loaded by another session.
            self.model = await get_whisper_model()

            self._started = True

    # ========================================================
    # Close
    # ========================================================

    async def close(self) -> None:
        """
        Close this transcriber.

        IMPORTANT:
            Closing a transcriber does NOT unload the
            shared WhisperModel.

        The model remains alive so other voice sessions
        can continue using it.

        Safe to call multiple times.
        """

        async with self._lock:
            if self._closed:
                return

            self._closed = True
            self._started = False

            # Do NOT set self.model = None here.
            #
            # The underlying WhisperModel is shared by
            # multiple transcribers.
            #
            # We simply close this session's wrapper.

    # ========================================================
    # Transcribe PCM
    # ========================================================

    async def transcribe_pcm(
        self,
        pcm_audio: bytes,
        sample_rate: int = 16000,
    ) -> Optional[TranscriptionResult]:
        """
        Transcribe PCM16 mono audio.

        The voice pipeline provides raw PCM bytes.

        The bytes are temporarily wrapped in a WAV file because
        Faster-Whisper can consume the WAV file directly.

        Empty audio returns None.
        """

        if self._closed:
            raise RuntimeError("Cannot transcribe with a closed transcriber.")

        if not self._started:
            raise RuntimeError("Transcriber has not been started.")

        if not pcm_audio:
            return None

        if len(pcm_audio) % 2 != 0:
            raise ValueError("PCM16 audio must contain an even number of bytes.")

        if sample_rate <= 0:
            raise ValueError("sample_rate must be greater than zero.")

        fd, path = tempfile.mkstemp(suffix=".wav")

        os.close(fd)

        try:

            def write_wav() -> None:

                with wave.open(
                    path,
                    "wb",
                ) as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(sample_rate)

                    wav.writeframes(pcm_audio)

            await asyncio.to_thread(write_wav)

            return await self.transcribe_file_async(path)

        finally:
            try:
                os.remove(path)

            except FileNotFoundError:
                pass

            except OSError:
                logger.exception("Failed to delete temporary voice audio file.")

    # ========================================================
    # Blocking file transcription
    # ========================================================

    def transcribe_file(
        self,
        audio_path: str,
    ) -> TranscriptionResult:

        if not audio_path:
            raise ValueError("audio_path must not be empty.")

        if self.model is None:
            raise RuntimeError("Whisper model is not initialized.")

        logger.debug(
            "Starting Whisper transcription path=%s",
            audio_path,
        )

        segments, info = self.model.transcribe(
            audio_path,
            language=WHISPER_LANGUAGE,
            vad_filter=True,
            condition_on_previous_text=False,
            beam_size=1,
            temperature=0.0,
        )

        texts: list[str] = []

        for segment in segments:
            text = segment.text.strip()

            if not text:
                continue

            logger.debug(
                "Whisper segment [%.2fs -> %.2fs]: %s",
                segment.start,
                segment.end,
                text,
            )

            texts.append(text)

        transcript = " ".join(texts).strip()

        if len(transcript) > MAX_TRANSCRIPT_LENGTH:
            transcript = transcript[:MAX_TRANSCRIPT_LENGTH]

            logger.warning(
                "Transcript truncated to %d characters",
                MAX_TRANSCRIPT_LENGTH,
            )

        language = getattr(
            info,
            "language",
            None,
        )

        language_probability = getattr(
            info,
            "language_probability",
            None,
        )

        duration_seconds = getattr(
            info,
            "duration",
            None,
        )

        return TranscriptionResult(
            text=transcript,
            language=language,
            language_probability=language_probability,
            duration_seconds=duration_seconds,
            has_speech=bool(transcript),
            speech_probability=language_probability,
        )

    # ========================================================
    # Async file transcription
    # ========================================================

    async def transcribe_file_async(
        self,
        audio_path: str,
    ) -> TranscriptionResult:

        if not audio_path:
            raise ValueError("audio_path must not be empty.")

        if self._closed:
            raise RuntimeError("Cannot transcribe with a closed transcriber.")

        if not self._started:
            raise RuntimeError("Transcriber has not been started.")

        return await asyncio.to_thread(
            self.transcribe_file,
            audio_path,
        )


# ============================================================
# Factory
# ============================================================


def whisper_transcriber() -> WhisperTranscriber:
    """
    Create a new WhisperTranscriber.

    The transcriber itself is session-scoped.

    The underlying WhisperModel is shared across all
    transcribers and loaded lazily on the first call to:

        await transcriber.start()
    """

    return WhisperTranscriber()
