"""
Audio buffering for the voice pipeline.

Responsibilities:
    - Store audio that has been accepted by the pipeline.
    - Track accumulated audio size.
    - Create safe snapshots for transcription.
    - Reset the current utterance.
    - Enforce maximum audio limits.
    - Clean up temporary files.

This module does NOT know about:
    - Whisper
    - VAD
    - turn detection
    - LangGraph
    - WebSockets
    - TTS
    - frontend events

Important:
    The caller is responsible for deciding whether an incoming
    audio chunk contains useful speech.

    The buffer should therefore NOT receive continuous silence
    merely because the microphone is continuously active.
"""

import asyncio
import os
from tempfile import NamedTemporaryFile
from typing import Optional

from .config import (
    AUDIO_SUFFIX,
    MAX_AUDIO_BYTES,
    MIN_AUDIO_BYTES,
)


class AudioBuffer:
    """
    Owns the temporary audio for the current user utterance.

    The microphone may remain active for the entire lifetime
    of the voice session, but this buffer only contains audio
    that the pipeline has decided to retain.

    A typical lifecycle is:

        start()
            ↓
        append(...)
            ↓
        snapshot()
            ↓
        reset()
            ↓
        append(...)
            ↓
        snapshot()
            ↓
        reset()

    The buffer itself does not determine whether audio is speech.
    That decision belongs to the VAD / pipeline layer.
    """

    def __init__(self) -> None:

        self.audio_path: Optional[str] = None

        self._audio_file = None

        self._audio_bytes = 0

        self._closed = False

        self._lock = asyncio.Lock()

    # ========================================================
    # Properties
    # ========================================================

    @property
    def audio_bytes(self) -> int:
        return self._audio_bytes

    @property
    def has_audio(self) -> bool:
        return self._audio_bytes > 0

    @property
    def closed(self) -> bool:
        return self._closed

    # ========================================================
    # Start
    # ========================================================

    async def start(self) -> None:
        """
        Create the temporary file for the current voice
        session.

        Calling start() multiple times is safe.
        """

        async with self._lock:
            if self._closed:
                raise RuntimeError("Cannot start a closed AudioBuffer.")

            if self._audio_file is not None:
                return

            temp_file = NamedTemporaryFile(
                delete=False,
                suffix=AUDIO_SUFFIX,
            )

            self.audio_path = temp_file.name
            self._audio_file = temp_file
            self._audio_bytes = 0

    # ========================================================
    # Append
    # ========================================================

    async def append(
        self,
        audio_chunk: bytes,
    ) -> None:
        """
        Append audio that has already been accepted by the
        speech pipeline.

        IMPORTANT:

        This method assumes the caller has already determined
        that this chunk is worth retaining.

        Silence should normally be filtered before reaching
        this method.
        """

        if not audio_chunk:
            return

        async with self._lock:
            if self._closed:
                raise RuntimeError("AudioBuffer is closed.")

            if self._audio_file is None:
                raise RuntimeError("AudioBuffer has not been started.")

            chunk_size = len(audio_chunk)

            # ------------------------------------------------
            # Enforce maximum utterance size.
            # ------------------------------------------------

            if self._audio_bytes + chunk_size > MAX_AUDIO_BYTES:
                raise ValueError("Maximum voice audio size exceeded.")

            # ------------------------------------------------
            # Append audio.
            # ------------------------------------------------

            self._audio_file.write(audio_chunk)
            self._audio_file.flush()

            self._audio_bytes += chunk_size

    # ========================================================
    # Snapshot
    # ========================================================

    async def snapshot(
        self,
    ) -> Optional[str]:
        """
        Create an independent snapshot of the current
        utterance.

        The active recording remains open.

        Returns:
            Temporary snapshot path or None when the current
            utterance does not contain enough audio.
        """

        async with self._lock:
            if self._closed:
                return None

            if not self.audio_path:
                return None

            if self._audio_file is None:
                return None

            if self._audio_bytes < MIN_AUDIO_BYTES:
                return None

            snapshot_path: Optional[str] = None

            try:
                self._audio_file.flush()

                snapshot = NamedTemporaryFile(
                    delete=False,
                    suffix=AUDIO_SUFFIX,
                )

                snapshot_path = snapshot.name
                snapshot.close()

                # --------------------------------------------
                # Copy current utterance.
                # --------------------------------------------

                with open(
                    self.audio_path,
                    "rb",
                ) as source:
                    with open(
                        snapshot_path,
                        "wb",
                    ) as destination:
                        while True:
                            data = source.read(1024 * 1024)

                            if not data:
                                break

                            destination.write(data)

                return snapshot_path

            except Exception:
                if snapshot_path and os.path.exists(snapshot_path):
                    try:
                        os.remove(snapshot_path)
                    except OSError:
                        pass

                raise

    # ========================================================
    # Reset
    # ========================================================

    async def reset(self) -> None:
        """
        Start a fresh utterance.

        The existing temporary recording is deleted and a
        new empty recording is created.

        This should normally happen after a completed user
        turn has been handed to the assistant.
        """

        async with self._lock:
            if self._closed:
                return

            # ------------------------------------------------
            # Close current file.
            # ------------------------------------------------

            if self._audio_file is not None:
                try:
                    self._audio_file.close()
                except Exception:
                    pass

                self._audio_file = None

            # ------------------------------------------------
            # Delete current recording.
            # ------------------------------------------------

            if self.audio_path:
                try:
                    os.remove(self.audio_path)

                except FileNotFoundError:
                    pass

                except OSError:
                    pass

            # ------------------------------------------------
            # Create a fresh recording.
            # ------------------------------------------------

            temp_file = NamedTemporaryFile(
                delete=False,
                suffix=AUDIO_SUFFIX,
            )

            self.audio_path = temp_file.name
            self._audio_file = temp_file
            self._audio_bytes = 0

    # ========================================================
    # Delete snapshot
    # ========================================================

    @staticmethod
    def delete_snapshot(
        snapshot_path: Optional[str],
    ) -> None:
        """
        Delete a temporary transcription snapshot.

        Safe to call with None or an already deleted path.
        """

        if not snapshot_path:
            return

        try:
            os.remove(snapshot_path)

        except FileNotFoundError:
            pass

        except OSError:
            pass

    # ========================================================
    # Close
    # ========================================================

    async def close(self) -> None:
        """
        Close the active recording and delete its temporary
        file.

        Safe to call multiple times.
        """

        async with self._lock:
            if self._closed:
                return

            self._closed = True

            # ------------------------------------------------
            # Close active file.
            # ------------------------------------------------

            if self._audio_file is not None:
                try:
                    self._audio_file.close()
                except Exception:
                    pass

                self._audio_file = None

            # ------------------------------------------------
            # Delete recording.
            # ------------------------------------------------

            if self.audio_path:
                try:
                    os.remove(self.audio_path)

                except FileNotFoundError:
                    pass

                except OSError:
                    pass

            # ------------------------------------------------
            # Reset state.
            # ------------------------------------------------

            self.audio_path = None
            self._audio_bytes = 0
