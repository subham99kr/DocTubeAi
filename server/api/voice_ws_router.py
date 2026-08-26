"""
Voice WebSocket API.

This module is intentionally thin.

It is responsible only for:
    - accepting the WebSocket
    - decoding incoming messages
    - passing audio to VoiceSession
    - handling session commands
    - closing the session

The WebSocket layer does NOT own:
    - VAD
    - transcription
    - turn detection
    - assistant execution
    - TTS
    - audio buffering
    - interruption logic
"""

from __future__ import annotations

import json
import logging
import time

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
)

from modules.voice.events import (
    connected,
    error,
)
from modules.voice.session import (
    VoiceSession,
)


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/voice",
    tags=["Voice"],
)


@router.websocket(
    "/ws/{session_id}"
)
async def voice_websocket(
    websocket: WebSocket,
    session_id: str,
):

    connection_started = time.perf_counter()

    await websocket.accept()

    logger.info(
        "WS_CONNECTED "
        "session=%s",
        session_id,
    )

    session = VoiceSession(
        websocket=websocket,
        session_id=session_id,
    )

    await session.send(
        connected()
    )

    logger.info(
        "WS_CONNECTED_EVENT_SENT "
        "session=%s",
    )

    audio_sequence = 0
    message_sequence = 0

    try:

        while session.running:

            message_sequence += 1

            message = await (
                websocket.receive()
            )

            # =================================================
            # Disconnect
            # =================================================

            if (
                message.get("type")
                == "websocket.disconnect"
            ):

                logger.info(
                    "WS_DISCONNECT_EVENT "
                    "session=%s "
                    "message_seq=%d",
                    session_id,
                    message_sequence,
                )

                break

            # =================================================
            # Binary audio
            # =================================================

            audio_chunk = (
                message.get("bytes")
            )

            if audio_chunk is not None:

                audio_sequence += 1

                logger.debug(
                    "WS_AUDIO_RECEIVED "
                    "session=%s "
                    "audio_seq=%d "
                    "bytes=%d",
                    session_id,
                    audio_sequence,
                    len(audio_chunk),
                )

                audio_started = (
                    time.perf_counter()
                )

                await session.receive_audio(
                    audio_chunk
                )

                audio_latency_ms = (
                    time.perf_counter()
                    - audio_started
                ) * 1000

                logger.debug(
                    "WS_AUDIO_HANDLED "
                    "session=%s "
                    "audio_seq=%d "
                    "bytes=%d "
                    "latency_ms=%.2f",
                    session_id,
                    audio_sequence,
                    len(audio_chunk),
                    audio_latency_ms,
                )

                continue

            # =================================================
            # Text message
            # =================================================

            text_data = (
                message.get("text")
            )

            if text_data is None:

                logger.debug(
                    "WS_EMPTY_MESSAGE "
                    "session=%s "
                    "message_seq=%d",
                    session_id,
                    message_sequence,
                )

                continue

            try:

                data = json.loads(
                    text_data
                )

            except json.JSONDecodeError:

                logger.warning(
                    "WS_INVALID_JSON "
                    "session=%s "
                    "message_seq=%d",
                    session_id,
                    message_sequence,
                )

                await session.send(
                    error(
                        "Invalid JSON.",
                        code="INVALID_JSON",
                    )
                )

                continue

            message_type = (
                data.get("type")
            )

            logger.debug(
                "WS_COMMAND_RECEIVED "
                "session=%s "
                "message_seq=%d "
                "type=%s",
                session_id,
                message_sequence,
                message_type,
            )

            # =================================================
            # Start
            # =================================================

            if message_type == "start_session":

                logger.info(
                    "WS_START_SESSION "
                    "session=%s",
                    session_id,
                )

                started = (
                    time.perf_counter()
                )

                await session.start()

                latency_ms = (
                    time.perf_counter()
                    - started
                ) * 1000

                logger.info(
                    "WS_START_SESSION_COMPLETE "
                    "session=%s "
                    "latency_ms=%.2f",
                    session_id,
                    latency_ms,
                )

                continue

            # =================================================
            # Ping
            # =================================================

            if message_type == "ping":

                logger.debug(
                    "WS_PING "
                    "session=%s",
                    session_id,
                )

                await session.send(
                    {
                        "type": "pong"
                    }
                )

                continue

            # =================================================
            # Close
            # =================================================

            if message_type == "close_session":

                logger.info(
                    "WS_CLOSE_REQUESTED "
                    "session=%s",
                    session_id,
                )

                break

            # =================================================
            # Unknown command
            # =================================================

            logger.warning(
                "WS_UNKNOWN_MESSAGE "
                "session=%s "
                "type=%s",
                session_id,
                message_type,
            )

            await session.send(
                error(
                    (
                        "Unknown message type: "
                        f"{message_type}"
                    ),
                    code="UNKNOWN_MESSAGE_TYPE",
                )
            )

    except WebSocketDisconnect:

        logger.info(
            "WS_DISCONNECTED "
            "session=%s",
            session_id,
        )

    except Exception:

        logger.exception(
            "WS_ERROR "
            "session=%s",
            session_id,
        )

    finally:

        logger.info(
            "WS_CLOSING_SESSION "
            "session=%s",
            session_id,
        )

        try:

            await session.close()

        finally:

            connection_duration_ms = (
                time.perf_counter()
                - connection_started
            ) * 1000

            logger.info(
                "WS_CLOSED "
                "session=%s "
                "audio_chunks=%d "
                "messages=%d "
                "duration_ms=%.2f",
                session_id,
                audio_sequence,
                message_sequence,
                connection_duration_ms,
            )