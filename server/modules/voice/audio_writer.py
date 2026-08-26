"""
Temporary audio writer for the voice pipeline.

File:
    voice/audio_writer.py

Responsibilities:
    - Convert PCM16 mono audio into WAV.
    - Create temporary WAV files for transcription.
    - Keep audio-file creation separate from Whisper.
    - Clean up temporary files safely.

This module does NOT know about:
    - Whisper
    - VAD
    - turn detection
    - assistants
    - LangGraph
    - WebSockets
    - TTS
"""

from __future__ import annotations

import asyncio
import os
import wave
from tempfile import NamedTemporaryFile
from typing import Optional


class AudioWriter:
    """
    Writes PCM16 mono audio into temporary WAV files.

    Expected input:

        PCM signed 16-bit
        mono
        little-endian

    Example:

        writer = AudioWriter(
            sample_rate=16000
        )

        path = await writer.write(
            pcm_audio
        )

        try:
            result = await transcriber.transcribe(
                path
            )
        finally:
            writer.delete(path)
    """

    def __init__(
        self,
        sample_rate: int = 16000,
    ) -> None:

        if sample_rate <= 0:

            raise ValueError(
                "sample_rate must be greater than zero."
            )

        self.sample_rate = sample_rate

    # ========================================================
    # Write
    # ========================================================

    async def write(
        self,
        pcm_audio: bytes,
    ) -> str:
        """
        Write PCM16 mono audio to a temporary WAV file.

        Args:
            pcm_audio:
                Signed 16-bit little-endian mono PCM.

        Returns:
            Path to the temporary WAV file.
        """

        if not pcm_audio:

            raise ValueError(
                "Cannot write empty audio."
            )

        return await asyncio.to_thread(
            self._write,
            pcm_audio,
        )

    # ========================================================
    # Blocking write
    # ========================================================

    def _write(
        self,
        pcm_audio: bytes,
    ) -> str:
        """
        Synchronous WAV creation.

        Runs outside the asyncio event loop.
        """

        temp_file = NamedTemporaryFile(
            delete=False,
            suffix=".wav",
        )

        path = temp_file.name

        temp_file.close()

        try:

            with wave.open(
                path,
                "wb",
            ) as wav_file:

                # ------------------------------------------------
                # PCM16 = 2 bytes per sample.
                # ------------------------------------------------

                wav_file.setnchannels(1)

                wav_file.setsampwidth(2)

                wav_file.setframerate(
                    self.sample_rate
                )

                wav_file.writeframes(
                    pcm_audio
                )

            return path

        except Exception:

            self.delete(path)

            raise

    # ========================================================
    # Delete
    # ========================================================

    @staticmethod
    def delete(
        audio_path: Optional[str],
    ) -> None:
        """
        Delete a temporary WAV file.

        Safe to call with:
            - None
            - an already deleted file
        """

        if not audio_path:
            return

        try:

            os.remove(
                audio_path
            )

        except FileNotFoundError:

            pass

        except OSError:

            # ------------------------------------------------
            # Cleanup failure must not crash the voice
            # pipeline.
            # ------------------------------------------------

            pass


# ============================================================
# Factory
# ============================================================


def create_audio_writer(
    sample_rate: int = 16000,
) -> AudioWriter:
    """
    Create the standard voice-pipeline audio writer.
    """

    return AudioWriter(
        sample_rate=sample_rate
    )