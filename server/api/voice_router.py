"""
Voice HTTP API.

This router contains HTTP-based voice endpoints.

Real-time voice communication belongs to:
    api/voice_ws_router.py
"""

import logging
import os
from tempfile import NamedTemporaryFile

from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
)

from modules.voice.transcription import (
    whisper_transcriber,
)

logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/voice",
    tags=["Voice"],
)


@router.post(
    "/transcribe"
)
async def transcribe_audio(
    audio: UploadFile = File(...),
):

    if not audio:

        raise HTTPException(
            status_code=400,
            detail="Audio file is required.",
        )

    audio_bytes = await audio.read()

    if not audio_bytes:

        raise HTTPException(
            status_code=400,
            detail="Uploaded audio is empty.",
        )

    temp_path = None

    try:

        with NamedTemporaryFile(
            delete=False,
            suffix=".webm",
        ) as temp_file:

            temp_file.write(
                audio_bytes
            )

            temp_path = (
                temp_file.name
            )

        result = await (
            whisper_transcriber.transcribe(
                temp_path
            )
        )

        return {
            "transcript": result.text,
            "language": result.language,
            "language_probability": (
                result.language_probability
            ),
        }

    except Exception as exc:

        logger.exception(
            "❌ HTTP transcription failed"
        )

        raise HTTPException(
            status_code=500,
            detail="Audio transcription failed.",
        ) from exc

    finally:

        if (
            temp_path
            and os.path.exists(
                temp_path
            )
        ):

            try:

                os.remove(
                    temp_path
                )

            except Exception:

                logger.warning(
                    "⚠️ Could not delete "
                    "temporary audio file: %s",
                    temp_path,
                )