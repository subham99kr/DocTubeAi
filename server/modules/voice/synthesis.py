"""
Text-to-Speech synthesis service.

Responsibilities:
    - Own the TTS engine.
    - Convert assistant text into audio.
    - Stream synthesized audio chunks.
    - Run blocking file work outside asyncio.
    - Normalize synthesis output.
    - Provide an async lifecycle.
    - Support cancellation.
    - Keep TTS implementation isolated from the voice pipeline.

This module does NOT know about:
    - WebSockets
    - microphone state
    - VAD
    - turn detection
    - Whisper
    - LangGraph
    - assistant state
    - frontend events
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import AsyncIterator, Optional

import edge_tts

logger = logging.getLogger(__name__)


# ============================================================
# Configuration
# ============================================================

DEFAULT_VOICE = os.getenv(
    "TTS_VOICE",
    "en-US-AriaNeural",
)

DEFAULT_RATE = os.getenv(
    "TTS_RATE",
    "+0%",
)

DEFAULT_VOLUME = os.getenv(
    "TTS_VOLUME",
    "+0%",
)

DEFAULT_PITCH = os.getenv(
    "TTS_PITCH",
    "+0Hz",
)


# ============================================================
# Result
# ============================================================


@dataclass(slots=True)
class SynthesisResult:
    """
    Result returned by the non-streaming synthesis method.

    This remains available for callers that need the complete
    audio buffer.
    """

    audio: bytes

    format: str = "mp3"

    sample_rate: Optional[int] = None

    duration_seconds: Optional[float] = None

    has_audio: bool = True


# ============================================================
# Synthesizer
# ============================================================


class SpeechSynthesizer:
    """
    Async lifecycle wrapper around Edge TTS.

    Two synthesis modes are supported:

        synthesize()
            Generate the complete audio buffer.

        synthesize_stream()
            Stream audio chunks as Edge TTS generates them.

    VoicePipeline uses synthesize_stream() for real-time
    assistant responses.
    """

    def __init__(
        self,
        voice: str = DEFAULT_VOICE,
        rate: str = DEFAULT_RATE,
        volume: str = DEFAULT_VOLUME,
        pitch: str = DEFAULT_PITCH,
    ) -> None:

        self.voice = voice
        self.rate = rate
        self.volume = volume
        self.pitch = pitch

        self._started = False
        self._closed = False

        # ----------------------------------------------------
        # Protect lifecycle state.
        # ----------------------------------------------------

        self._lock = asyncio.Lock()

        # ----------------------------------------------------
        # Currently running synthesis operation.
        #
        # This may be either:
        #
        #     synthesize()
        #
        # or:
        #
        #     synthesize_stream()
        #
        # VoicePipeline uses this for interruption.
        # ----------------------------------------------------

        self._synthesis_task: Optional[asyncio.Task] = None

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
        Initialize the synthesizer.

        Edge TTS does not require a heavyweight local model
        so startup is intentionally lightweight.
        """

        async with self._lock:
            if self._closed:
                raise RuntimeError("Cannot start a closed synthesizer.")

            if self._started:
                return

            self._started = True

            logger.info(
                "🔊 Speech synthesizer started voice=%s rate=%s volume=%s pitch=%s",
                self.voice,
                self.rate,
                self.volume,
                self.pitch,
            )

    # ========================================================
    # Cancel
    # ========================================================

    async def cancel(self) -> None:
        """
        Cancel the currently running synthesis operation.

        Safe to call when nothing is being synthesized.
        """

        task = self._synthesis_task

        if task is None:
            return

        # ----------------------------------------------------
        # Clear the reference immediately.
        # ----------------------------------------------------

        self._synthesis_task = None

        if task.done():
            return

        logger.info("🛑 Cancelling speech synthesis.")

        task.cancel()

        try:
            await task

        except asyncio.CancelledError:
            pass

        except Exception:
            logger.exception("Error while cancelling speech synthesis.")

    # ========================================================
    # Close
    # ========================================================

    async def close(self) -> None:
        """
        Close the synthesizer.

        Safe to call multiple times.
        """

        await self.cancel()

        async with self._lock:
            if self._closed:
                return

            self._closed = True
            self._started = False

            logger.info("🔌 Speech synthesizer closed.")

    # ========================================================
    # Complete synthesis
    # ========================================================

    async def synthesize(
        self,
        text: str,
    ) -> Optional[SynthesisResult]:
        """
        Generate the complete audio buffer.

        This method is retained for callers that explicitly
        want the entire synthesized result.

        VoicePipeline uses synthesize_stream() for real-time
        responses.
        """

        if self._closed:
            raise RuntimeError("Cannot synthesize with a closed synthesizer.")

        if not self._started:
            raise RuntimeError("Synthesizer has not been started.")

        text = self._normalize_text(text)

        if not text:
            return None

        await self.cancel()

        logger.debug(
            "Starting complete speech synthesis text_length=%d",
            len(text),
        )

        task = asyncio.create_task(self._synthesize_edge_tts(text))

        self._synthesis_task = task

        try:
            return await task

        except asyncio.CancelledError:
            logger.debug("Speech synthesis task cancelled.")

            raise

        finally:
            if self._synthesis_task is task:
                self._synthesis_task = None

    # ========================================================
    # Complete Edge TTS synthesis
    # ========================================================

    async def _synthesize_edge_tts(
        self,
        text: str,
    ) -> SynthesisResult:
        """
        Generate a complete MP3 using Edge TTS.
        """

        fd, path = tempfile.mkstemp(suffix=".mp3")

        os.close(fd)

        try:
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                volume=self.volume,
                pitch=self.pitch,
            )

            await communicate.save(path)

            await asyncio.sleep(0)

            audio = await asyncio.to_thread(
                self._read_file,
                path,
            )

            if not audio:
                raise RuntimeError("TTS returned empty audio.")

            logger.debug(
                "Speech synthesis completed bytes=%d",
                len(audio),
            )

            return SynthesisResult(
                audio=audio,
                format="mp3",
                has_audio=True,
            )

        except asyncio.CancelledError:
            logger.debug("Speech synthesis cancelled.")

            raise

        except Exception:
            logger.exception("❌ Speech synthesis failed.")

            raise

        finally:
            with contextlib.suppress(
                FileNotFoundError,
                OSError,
            ):
                os.remove(path)

    # ========================================================
    # Streaming synthesis
    # ========================================================

    async def synthesize_stream(
        self,
        text: str,
    ) -> AsyncIterator[bytes]:
        """
        Stream synthesized audio chunks.

        The caller receives each audio chunk as soon as
        Edge TTS produces it.

        Example:

            async for audio in synthesizer.synthesize_stream(
                "Hello there."
            ):
                await send_audio(audio)

        The entire generated audio is therefore NOT buffered
        before being sent to the client.
        """

        if self._closed:
            raise RuntimeError("Cannot synthesize with a closed synthesizer.")

        if not self._started:
            raise RuntimeError("Synthesizer has not been started.")

        text = self._normalize_text(text)

        if not text:
            return

        # ----------------------------------------------------
        # Cancel any previous synthesis operation.
        # ----------------------------------------------------

        await self.cancel()

        logger.debug(
            "Starting streaming speech synthesis text_length=%d",
            len(text),
        )

        # ----------------------------------------------------
        # The actual streaming generator must run inside a
        # task so interrupt_assistant() can cancel it.
        # ----------------------------------------------------

        queue: asyncio.Queue[Optional[bytes]] = asyncio.Queue()

        async def producer() -> None:

            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                volume=self.volume,
                pitch=self.pitch,
            )

            try:
                async for chunk in communicate.stream():
                    await asyncio.sleep(0)

                    if chunk.get("type") != "audio":
                        continue

                    audio = chunk.get("data")

                    if not audio:
                        continue

                    await queue.put(audio)

            except asyncio.CancelledError:
                logger.debug("Streaming speech synthesis producer cancelled.")

                raise

            finally:
                # ------------------------------------------------
                # None means the producer has finished.
                # ------------------------------------------------

                await queue.put(None)

        task = asyncio.create_task(producer())

        self._synthesis_task = task

        try:
            while True:
                audio = await queue.get()

                if audio is None:
                    break

                yield audio

        except asyncio.CancelledError:
            logger.debug("Streaming speech synthesis cancelled.")

            task.cancel()

            await asyncio.gather(
                task,
                return_exceptions=True,
            )

            raise

        finally:
            # ------------------------------------------------
            # If the stream ended normally, wait for producer.
            # ------------------------------------------------

            if not task.done():
                await asyncio.gather(
                    task,
                    return_exceptions=True,
                )

            if self._synthesis_task is task:
                self._synthesis_task = None

    # ========================================================
    # Text normalization
    # ========================================================

    @staticmethod
    def _normalize_text(
        text: str,
    ) -> str:
        """
        Normalize assistant output before synthesis.
        """

        if not text:
            return ""

        text = str(text).strip()

        if not text:
            return ""

        text = " ".join(text.split())

        return text

    # ========================================================
    # File helper
    # ========================================================

    @staticmethod
    def _read_file(
        path: str,
    ) -> bytes:

        with open(
            path,
            "rb",
        ) as file:
            return file.read()


# ============================================================
# Factory
# ============================================================


def speech_synthesizer(
    voice: str = DEFAULT_VOICE,
) -> SpeechSynthesizer:
    """
    Create a SpeechSynthesizer.

    The TTS engine is initialized only after:

        await synthesizer.start()
    """

    return SpeechSynthesizer(
        voice=voice,
    )
