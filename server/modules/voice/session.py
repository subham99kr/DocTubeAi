"""
Voice session orchestration.

VoiceSession owns only the WebSocket/session boundary.

It does NOT know about:

- Whisper
- VAD internals
- TurnDetector internals
- LangGraph
- TTS internals
- VoiceAssistant internals

Those responsibilities belong to VoicePipeline.

VoiceSession simply:

    WebSocket
        ↕
    VoicePipeline callbacks
        ↕
    WebSocket events
"""

from __future__ import annotations

import logging

from fastapi import WebSocket

from .events import (
    assistant_audio,
    assistant_completed,
    assistant_started,
    assistant_status,
    assistant_text,
    error,
    session_started,
    transcript_final,
    transcript_partial,
    user_speech_started,
    user_turn_complete,
)
from .models import (
    SpeechStarted,
    TranscriptChanged,
    TurnCompleted,
)
from .pipeline import VoicePipeline

logger = logging.getLogger(__name__)


# ============================================================
# VoiceSession
# ============================================================


class VoiceSession:
    def __init__(
        self,
        websocket: WebSocket,
        session_id: str,
        pipeline: VoicePipeline | None = None,
    ) -> None:

        self.websocket = websocket
        self.session_id = session_id

        self.running = True
        self.started = False

        # ----------------------------------------------------
        # VoicePipeline
        #
        # VoiceSession only connects pipeline callbacks to
        # WebSocket events.
        # ----------------------------------------------------

        self.pipeline = pipeline or VoicePipeline(
            session_id=session_id,
            on_speech_started=(self._on_speech_started),
            on_transcript_changed=(self._on_transcript_changed),
            on_turn_complete=(self._on_turn_complete),
            on_assistant_started=(self._on_assistant_started),
            on_assistant_status=(self._on_assistant_status),
            on_assistant_text=(self._on_assistant_text),
            on_assistant_audio=(self._on_assistant_audio),
            on_assistant_completed=(self._on_assistant_completed),
            on_assistant_error=(self._on_assistant_error),
        )

    # ========================================================
    # Send event
    # ========================================================

    async def send(
        self,
        payload: dict,
    ) -> None:

        if not self.running:
            return

        try:
            await self.websocket.send_json(payload)

        except Exception:
            logger.exception(
                "Failed to send voice event session=%s",
                self.session_id,
            )

            self.running = False

    # ========================================================
    # Start
    # ========================================================

    async def start(self) -> None:

        if self.started:
            return

        if not self.running:
            return

        self.started = True

        logger.info(
            "Voice session starting session=%s",
            self.session_id,
        )

        try:
            await self.pipeline.start()

        except Exception:
            self.started = False

            logger.exception(
                "Failed to start voice pipeline session=%s",
                self.session_id,
            )

            await self.send(
                error(
                    "Failed to start voice pipeline.",
                    code="PIPELINE_START_FAILED",
                )
            )

            raise

        await self.send(session_started())

        logger.info(
            "Voice session started session=%s",
            self.session_id,
        )

    # ========================================================
    # Receive audio
    # ========================================================

    async def receive_audio(
        self,
        audio_chunk: bytes,
    ) -> None:

        if not self.running:
            return

        if not self.started:
            return

        if not audio_chunk:
            return

        try:
            await self.pipeline.receive_audio(audio_chunk)

        except ValueError as exc:
            logger.warning(
                "Audio limit exceeded session=%s",
                self.session_id,
            )

            await self.send(
                error(
                    str(exc),
                    code="AUDIO_LIMIT_EXCEEDED",
                )
            )

            await self.close()

        except Exception:
            logger.exception(
                "Failed to process voice audio session=%s",
                self.session_id,
            )

            await self.send(
                error(
                    "Failed to process audio.",
                    code="AUDIO_PROCESSING_FAILED",
                )
            )

    # ========================================================
    # User speech started
    # ========================================================

    async def _on_speech_started(
        self,
        event: SpeechStarted,
    ) -> None:

        if not self.running:
            return

        await self.send(user_speech_started(event.turn_id))

    # ========================================================
    # Partial transcript
    # ========================================================

    async def _on_transcript_changed(
        self,
        event: TranscriptChanged,
    ) -> None:

        if not self.running:
            return

        await self.send(
            transcript_partial(
                event.text,
                event.turn_id,
            )
        )

    # ========================================================
    # User turn complete
    # ========================================================

    async def _on_turn_complete(
        self,
        event: TurnCompleted,
    ) -> None:

        if not self.running:
            return

        await self.send(
            transcript_final(
                event.text,
                event.turn_id,
            )
        )

        await self.send(
            user_turn_complete(
                event.text,
                event.turn_id,
            )
        )

    # ========================================================
    # Assistant started
    # ========================================================

    async def _on_assistant_started(
        self,
        turn_id: int,
    ) -> None:

        if not self.running:
            return

        await self.send(assistant_started(turn_id))

    # ========================================================
    # Assistant status
    # ========================================================

    async def _on_assistant_status(
        self,
        message: str,
        turn_id: int,
    ) -> None:

        if not self.running:
            return

        message = message.strip()

        if not message:
            return

        logger.debug(
            "Sending assistant status session=%s turn=%s status=%r",
            self.session_id,
            turn_id,
            message,
        )

        await self.send(
            assistant_status(
                message,
                turn_id,
            )
        )

    # ========================================================
    # Assistant text
    # ========================================================

    async def _on_assistant_text(
        self,
        text: str,
        turn_id: int,
    ) -> None:

        if not self.running:
            return

        if not text:
            return

        await self.send(
            assistant_text(
                text,
                turn_id,
            )
        )

    # ========================================================
    # Assistant audio
    # ========================================================

    async def _on_assistant_audio(
        self,
        audio: bytes,
        turn_id: int,
    ) -> None:

        if not self.running:
            return

        if not audio:
            return

        await self.send(
            assistant_audio(
                audio,
                turn_id,
            )
        )

    # ========================================================
    # Assistant completed
    # ========================================================

    async def _on_assistant_completed(
        self,
        turn_id: int,
    ) -> None:

        if not self.running:
            return

        await self.send(assistant_completed(turn_id))

    # ========================================================
    # Assistant error
    # ========================================================

    async def _on_assistant_error(
        self,
        turn_id: int,
        exc: Exception,
    ) -> None:

        logger.error(
            "Assistant failed session=%s turn=%s",
            self.session_id,
            turn_id,
            exc_info=(
                type(exc),
                exc,
                exc.__traceback__,
            ),
        )

        if not self.running:
            return

        await self.send(
            error(
                "Assistant processing failed.",
                code="ASSISTANT_FAILED",
            )
        )

    # ========================================================
    # Close
    # ========================================================

    async def close(self) -> None:

        if not self.running:
            return

        logger.info(
            "Closing voice session session=%s",
            self.session_id,
        )

        self.running = False

        try:
            await self.pipeline.close()

        except Exception:
            logger.exception(
                "Failed to close voice pipeline session=%s",
                self.session_id,
            )

        self.started = False

        logger.info(
            "Voice session closed session=%s",
            self.session_id,
        )
