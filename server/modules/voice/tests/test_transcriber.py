"""
Tests for the voice transcription layer.

File:
    voice/tests/test_transcriber.py

These tests verify the transcription interface and lifecycle
without requiring a real Whisper inference during every test.

The transcription layer contract is:

    transcriber factory
          ↓
    start()
          ↓
    PCM audio
          ↓
    TranscriptionResult
          ↓
    close()
"""

import pytest
from modules.voice.models import TranscriptionResult
from modules.voice.transcription import (
    WhisperTranscriber,
    whisper_transcriber,
)

# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def transcriber():
    """
    Create a lightweight transcriber instance.

    The factory must not load the Whisper model.
    """

    return whisper_transcriber()


# ============================================================
# Factory
# ============================================================


def test_factory_returns_transcriber():
    """
    The factory should return a WhisperTranscriber instance.
    """

    transcriber = whisper_transcriber()

    assert isinstance(
        transcriber,
        WhisperTranscriber,
    )

    assert transcriber.started is False

    assert transcriber.closed is False


# ============================================================
# Lifecycle
# ============================================================


@pytest.mark.anyio
async def test_transcriber_can_start(
    transcriber,
):
    """
    Transcriber should initialize successfully.

    A fake model is injected so the test does not download
    or load a real Whisper model.
    """

    class FakeModel:
        pass

    transcriber.model = FakeModel()

    await transcriber.start()

    assert transcriber.started is True

    assert transcriber.closed is False


@pytest.mark.anyio
async def test_transcriber_can_close(
    transcriber,
):
    """
    Transcriber should close cleanly.
    """

    class FakeModel:
        pass

    transcriber.model = FakeModel()

    await transcriber.start()

    await transcriber.close()

    assert transcriber.closed is True

    assert transcriber.started is False


@pytest.mark.anyio
async def test_close_is_idempotent(
    transcriber,
):
    """
    Calling close multiple times should be safe.
    """

    class FakeModel:
        pass

    transcriber.model = FakeModel()

    await transcriber.start()

    await transcriber.close()

    await transcriber.close()

    assert transcriber.closed is True

    assert transcriber.started is False


# ============================================================
# Empty audio
# ============================================================


@pytest.mark.anyio
async def test_empty_audio_returns_no_transcription(
    transcriber,
):
    """
    Empty audio should not be sent to Whisper.
    """

    class FakeModel:
        def transcribe(self, *args, **kwargs):
            raise AssertionError(
                "Whisper should not be called for empty audio."
            )

    transcriber.model = FakeModel()

    await transcriber.start()

    result = await transcriber.transcribe(
        b""
    )

    assert result is None


# ============================================================
# Invalid lifecycle
# ============================================================


@pytest.mark.anyio
async def test_transcribe_before_start_is_rejected(
    transcriber,
):
    """
    Transcription before startup should be rejected.
    """

    with pytest.raises(RuntimeError):

        await transcriber.transcribe(
            b"\x00\x00"
        )


@pytest.mark.anyio
async def test_transcribe_after_close_is_rejected(
    transcriber,
):
    """
    Transcription after shutdown should be rejected.
    """

    class FakeModel:
        pass

    transcriber.model = FakeModel()

    await transcriber.start()

    await transcriber.close()

    with pytest.raises(RuntimeError):

        await transcriber.transcribe(
            b"\x00\x00"
        )


@pytest.mark.anyio
async def test_start_after_close_is_rejected(
    transcriber,
):
    """
    A closed transcriber cannot be restarted.
    """

    class FakeModel:
        pass

    transcriber.model = FakeModel()

    await transcriber.start()

    await transcriber.close()

    with pytest.raises(RuntimeError):

        await transcriber.start()


# ============================================================
# Start idempotency
# ============================================================


@pytest.mark.anyio
async def test_start_is_idempotent(
    transcriber,
):
    """
    Calling start() multiple times should be safe.
    """

    class FakeModel:
        pass

    model = FakeModel()

    transcriber.model = model

    await transcriber.start()

    await transcriber.start()

    assert transcriber.started is True

    assert transcriber.model is model


# ============================================================
# Result contract
# ============================================================


def test_transcription_result_contract():
    """
    Verify the shared transcription result model.
    """

    result = TranscriptionResult(
        text="hello world",
        language="en",
        language_probability=0.98,
        duration_seconds=1.5,
    )

    assert result.text == "hello world"

    assert result.language == "en"

    assert (
        result.language_probability
        == 0.98
    )

    assert (
        result.duration_seconds
        == 1.5
    )