"""
Voice pipeline configuration.

All voice-specific configuration lives here.
"""

import os


# ============================================================
# Faster-Whisper
# ============================================================

WHISPER_MODEL = os.getenv(
    "VOICE_WHISPER_MODEL",
    "small",
)

WHISPER_DEVICE = os.getenv(
    "VOICE_WHISPER_DEVICE",
    "cpu",
)

WHISPER_COMPUTE_TYPE = os.getenv(
    "VOICE_WHISPER_COMPUTE_TYPE",
    "int8",
)

WHISPER_LANGUAGE = os.getenv(
    "VOICE_WHISPER_LANGUAGE",
    "en",
)


# ============================================================
# Audio
# ============================================================

AUDIO_SUFFIX = ".webm"

MIN_AUDIO_BYTES = int(
    os.getenv(
        "VOICE_MIN_AUDIO_BYTES",
        "10000",
    )
)

MAX_AUDIO_BYTES = int(
    os.getenv(
        "VOICE_MAX_AUDIO_BYTES",
        str(100 * 1024 * 1024),
    )
)


# ============================================================
# Voice Activity Detection
# ============================================================

# ------------------------------------------------------------
# Minimum amount of audio required before considering
# a speech segment for transcription.
# ------------------------------------------------------------

VAD_MIN_SPEECH_SECONDS = float(
    os.getenv(
        "VOICE_VAD_MIN_SPEECH_SECONDS",
        "0.15",
    )
)

# ------------------------------------------------------------
# How long silence must persist before VAD considers the
# speech segment finished.
# ------------------------------------------------------------

VAD_SILENCE_SECONDS = float(
    os.getenv(
        "VOICE_VAD_SILENCE_SECONDS",
        "0.50",
    )
)

# ------------------------------------------------------------
# Small amount of audio kept before detected speech.
#
# This prevents clipping the first phoneme.
# ------------------------------------------------------------

VAD_PRE_SPEECH_SECONDS = float(
    os.getenv(
        "VOICE_VAD_PRE_SPEECH_SECONDS",
        "0.30",
    )
)

# ------------------------------------------------------------
# Small amount of trailing audio kept after speech ends.
#
# This prevents clipping the last word.
# ------------------------------------------------------------

VAD_POST_SPEECH_SECONDS = float(
    os.getenv(
        "VOICE_VAD_POST_SPEECH_SECONDS",
        "0.30",
    )
)

# ------------------------------------------------------------
# Energy threshold for the lightweight audio gate.
#
# This is intentionally only a gate, not the final speech
# detector.
# ------------------------------------------------------------

VAD_ENERGY_THRESHOLD = float(
    os.getenv(
        "VOICE_VAD_ENERGY_THRESHOLD",
        "0.01",
    )
)


# ============================================================
# Transcription
# ============================================================

TRANSCRIPTION_INTERVAL = float(
    os.getenv(
        "VOICE_TRANSCRIPTION_INTERVAL",
        "0.25",
    )
)

# ------------------------------------------------------------
# Do not start another Whisper inference while one is active.
# ------------------------------------------------------------

TRANSCRIPTION_MAX_CONCURRENT = int(
    os.getenv(
        "VOICE_TRANSCRIPTION_MAX_CONCURRENT",
        "1",
    )
)


# ============================================================
# Turn Detection
# ============================================================

TURN_SILENCE_SECONDS = float(
    os.getenv(
        "VOICE_TURN_SILENCE_SECONDS",
        "1.0",
    )
)


# ============================================================
# Interruption
# ============================================================

# ------------------------------------------------------------
# Minimum speech duration before interrupting the assistant.
#
# This prevents tiny noises from stopping TTS.
# ------------------------------------------------------------

INTERRUPTION_MIN_SPEECH_SECONDS = float(
    os.getenv(
        "VOICE_INTERRUPTION_MIN_SPEECH_SECONDS",
        "0.30",
    )
)


# ------------------------------------------------------------
# Whether user speech can interrupt assistant output.
# ------------------------------------------------------------

INTERRUPTION_ENABLED = (
    os.getenv(
        "VOICE_INTERRUPTION_ENABLED",
        "true",
    ).lower()
    == "true"
)


# ============================================================
# Session
# ============================================================

MAX_SESSION_SECONDS = float(
    os.getenv(
        "VOICE_MAX_SESSION_SECONDS",
        "0",
    )
)


# ============================================================
# Assistant
# ============================================================

ASSISTANT_TIMEOUT_SECONDS = float(
    os.getenv(
        "VOICE_ASSISTANT_TIMEOUT_SECONDS",
        "120",
    )
)


# ============================================================
# Safety
# ============================================================

MAX_TRANSCRIPT_LENGTH = int(
    os.getenv(
        "VOICE_MAX_TRANSCRIPT_LENGTH",
        "20000",
    )
)