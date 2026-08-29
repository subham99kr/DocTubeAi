"""
Audio decoding for the voice pipeline.

File:
    voice/audio_decoder.py

Responsibilities:
    - Decode browser WebM/Opus audio into PCM16.
    - Maintain a continuous WebM stream across MediaRecorder chunks.
    - Normalize audio to mono.
    - Normalize the sample rate.
    - Produce fixed-size PCM frames for VAD.
    - Preserve incomplete PCM frames until enough samples arrive.

This module does NOT know about:
    - Whisper
    - VAD decisions
    - turn detection
    - assistants
    - LangGraph
    - WebSockets
    - TTS
    - frontend events
"""

from __future__ import annotations

import asyncio
import io
import logging
from typing import Optional

import av
import numpy as np

logger = logging.getLogger(__name__)


class AudioDecoder:
    """
    Convert a continuous browser WebM/Opus stream into
    fixed-size PCM16 frames.

    Target format:

        sample rate : 16 kHz
        channels    : 1
        sample type : signed 16-bit PCM
        byte order  : little endian

    Important:

    MediaRecorder with timeslice produces multiple Blob
    objects from ONE logical WebM recording.

    A later Blob is not guaranteed to contain a complete
    WebM container by itself.

    Therefore this decoder accumulates the incoming WebM
    bytes and decodes the accumulated stream.

        MediaRecorder chunk
              ↓
        WebM buffer
              ↓
        PyAV
              ↓
        PCM16
              ↓
        fixed-size frames
              ↓
        VAD
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 20,
    ) -> None:

        if sample_rate <= 0:
            raise ValueError("sample_rate must be greater than zero.")

        if frame_duration_ms <= 0:
            raise ValueError("frame_duration_ms must be greater than zero.")

        samples_per_frame = sample_rate * frame_duration_ms / 1000

        if not samples_per_frame.is_integer():
            raise ValueError(
                "sample_rate and frame_duration_ms "
                "must produce an integer number of samples."
            )

        self.sample_rate = sample_rate

        self.frame_duration_ms = frame_duration_ms

        self.samples_per_frame = int(samples_per_frame)

        self.frame_size_bytes = self.samples_per_frame * 2

        # ----------------------------------------------------
        # Continuous WebM/Opus stream.
        #
        # MediaRecorder chunks are appended here instead of
        # being treated as independent audio files.
        # ----------------------------------------------------

        self._webm_buffer = bytearray()

        # ----------------------------------------------------
        # Number of PCM samples already emitted.
        #
        # Because the accumulated WebM stream is decoded again
        # when new data arrives, this prevents already-emitted
        # PCM from being returned repeatedly.
        # ----------------------------------------------------

        self._decoded_samples = 0

        # ----------------------------------------------------
        # PCM that has not yet formed a complete VAD frame.
        # ----------------------------------------------------

        self._pcm_buffer = bytearray()

        self._closed = False

        self._lock = asyncio.Lock()

    # ========================================================
    # Properties
    # ========================================================

    @property
    def buffered_bytes(self) -> int:
        """
        Number of PCM bytes waiting for a complete frame.
        """

        return len(self._pcm_buffer)

    @property
    def buffered_samples(self) -> int:
        """
        Number of PCM samples waiting for a complete frame.
        """

        return len(self._pcm_buffer) // 2

    @property
    def webm_buffered_bytes(self) -> int:
        """
        Number of WebM bytes currently retained.
        """

        return len(self._webm_buffer)

    @property
    def closed(self) -> bool:
        return self._closed

    # ========================================================
    # Decode
    # ========================================================

    async def decode(
        self,
        audio_chunk: bytes,
    ) -> list[bytes]:
        """
        Add a MediaRecorder WebM/Opus chunk to the continuous
        stream and return any newly decoded PCM frames.

        A chunk is NOT assumed to be independently decodable.
        """

        if not audio_chunk:
            return []

        async with self._lock:
            if self._closed:
                raise RuntimeError("AudioDecoder is closed.")

            # ------------------------------------------------
            # Append the new MediaRecorder chunk to the
            # continuous WebM stream.
            # ------------------------------------------------

            self._webm_buffer.extend(audio_chunk)

            try:
                pcm = await asyncio.to_thread(
                    self._decode_stream,
                    bytes(self._webm_buffer),
                )

            except av.error.InvalidDataError:
                # ------------------------------------------------
                # The accumulated stream may still be incomplete.
                #
                # This is normal while MediaRecorder is producing
                # chunks. Do NOT kill the voice session.
                # ------------------------------------------------

                logger.debug("Incomplete WebM stream; waiting for more audio data.")

                return []

            except Exception:
                logger.exception("Audio decoding failed.")

                raise

            if pcm is None or pcm.size == 0:
                return []

            # ------------------------------------------------
            # PyAV decoded the accumulated stream from the
            # beginning.
            #
            # Only return samples that have not already been
            # emitted.
            # ------------------------------------------------

            total_samples = len(pcm)

            if total_samples <= self._decoded_samples:
                return []

            new_pcm = pcm[self._decoded_samples :]

            self._decoded_samples = total_samples

            self._pcm_buffer.extend(new_pcm.tobytes())

            return self._extract_frames()

    # ========================================================
    # Blocking stream decode
    # ========================================================

    def _decode_stream(
        self,
        audio_bytes: bytes,
    ) -> np.ndarray:
        """
        Decode the accumulated WebM/Opus stream.

        This function executes outside the asyncio event loop.

        Returns:
            Mono int16 PCM samples.
        """

        if not audio_bytes:
            return np.empty(
                0,
                dtype=np.int16,
            )

        container: Optional[av.container.InputContainer] = None

        try:
            container = av.open(
                io.BytesIO(audio_bytes),
                mode="r",
            )

            audio_stream = self._find_audio_stream(container)

            if audio_stream is None:
                return np.empty(
                    0,
                    dtype=np.int16,
                )

            resampler = av.audio.resampler.AudioResampler(
                format="s16",
                layout="mono",
                rate=self.sample_rate,
            )

            samples: list[np.ndarray] = []

            for frame in container.decode(audio_stream):
                converted_frames = resampler.resample(frame)

                if converted_frames is None:
                    continue

                if not isinstance(
                    converted_frames,
                    list,
                ):
                    converted_frames = [converted_frames]

                for output_frame in converted_frames:
                    array = output_frame.to_ndarray()

                    if array.size == 0:
                        continue

                    array = np.asarray(
                        array,
                        dtype=np.int16,
                    )

                    # AudioResampler is configured
                    # for mono.

                    array = array.reshape(-1)

                    samples.append(array)

            if not samples:
                return np.empty(
                    0,
                    dtype=np.int16,
                )

            return np.concatenate(samples)

        finally:
            if container is not None:
                try:
                    container.close()

                except Exception:
                    logger.debug(
                        "Failed to close audio container.",
                        exc_info=True,
                    )

    # ========================================================
    # Find audio stream
    # ========================================================

    @staticmethod
    def _find_audio_stream(
        container: av.container.InputContainer,
    ):
        """
        Return the first audio stream in the container.
        """

        for stream in container.streams:
            if stream.type == "audio":
                return stream

        return None

    # ========================================================
    # Extract fixed-size frames
    # ========================================================

    def _extract_frames(
        self,
    ) -> list[bytes]:
        """
        Extract complete PCM16 frames.

        Example:

            decoded PCM
                 │
                 ├── 20 ms ──► frame
                 ├── 20 ms ──► frame
                 ├── 20 ms ──► frame
                 │
                 └── partial ─► retained
        """

        frames: list[bytes] = []

        while len(self._pcm_buffer) >= self.frame_size_bytes:
            frame = bytes(self._pcm_buffer[: self.frame_size_bytes])

            del self._pcm_buffer[: self.frame_size_bytes]

            frames.append(frame)

        return frames

    # ========================================================
    # Flush
    # ========================================================

    async def flush(
        self,
    ) -> list[bytes]:
        """
        Return the remaining PCM samples.

        Normally called when the voice session/recording
        segment ends.
        """

        async with self._lock:
            if self._closed:
                return []

            if not self._pcm_buffer:
                return []

            frame = bytes(self._pcm_buffer)

            self._pcm_buffer.clear()

            return [frame]

    # ========================================================
    # Reset
    # ========================================================

    async def reset(
        self,
    ) -> None:
        """
        Reset the current audio stream.

        A reset starts a completely new MediaRecorder stream.
        """

        async with self._lock:
            if self._closed:
                return

            self._webm_buffer.clear()

            self._decoded_samples = 0

            self._pcm_buffer.clear()

    # ========================================================
    # Close
    # ========================================================

    async def close(
        self,
    ) -> None:
        """
        Close the decoder.

        Safe to call multiple times.
        """

        async with self._lock:
            if self._closed:
                return

            self._closed = True

            self._webm_buffer.clear()

            self._decoded_samples = 0

            self._pcm_buffer.clear()

    # ========================================================
    # Factory
    # ========================================================


def create_audio_decoder(
    sample_rate: int = 16000,
    frame_duration_ms: int = 20,
) -> AudioDecoder:
    """
    Create the standard voice-pipeline audio decoder.
    """

    return AudioDecoder(
        sample_rate=sample_rate,
        frame_duration_ms=frame_duration_ms,
    )
