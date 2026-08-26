"""
Unit tests for the Voice HTTP API.

These tests isolate the HTTP router from the real Whisper
transcription implementation.

They verify:

    - valid audio upload
    - successful transcription response
    - empty audio rejection
    - transcription failure handling
    - temporary file cleanup
    - uploaded audio reaching the transcriber
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.voice_router import router


# ============================================================
# Fake transcriber
# ============================================================


class FakeTranscriptionResult:
    """Minimal transcription result used by the HTTP tests."""

    def __init__(
        self,
        text: str = "hello from voice api",
        language: str = "en",
        language_probability: float = 0.99,
    ):
        self.text = text
        self.language = language
        self.language_probability = (
            language_probability
        )


class FakeWhisperTranscriber:
    """Deterministic fake Whisper transcriber."""

    def __init__(
        self,
        result=None,
        error: Exception | None = None,
    ):
        self.result = (
            result
            or FakeTranscriptionResult()
        )

        self.error = error
        self.calls = []

    async def transcribe(
        self,
        audio_path: str,
    ):

        self.calls.append(
            audio_path
        )

        if self.error is not None:
            raise self.error

        return self.result


# ============================================================
# App fixture
# ============================================================


@pytest.fixture
def app():

    application = FastAPI()

    application.include_router(
        router
    )

    return application


@pytest.fixture
def client(app):

    return TestClient(
        app
    )


# ============================================================
# Helpers
# ============================================================


def get_router_module():

    """
    Return the module containing the HTTP router.

    The imported `router` object belongs to this module.
    """

    return __import__(
        "api.voice_router",
        fromlist=["router"],
    )


# ============================================================
# Test 1
# ============================================================


def test_valid_audio_returns_transcription(
    client,
    monkeypatch,
):

    fake_transcriber = (
        FakeWhisperTranscriber(
            result=FakeTranscriptionResult(
                text="hello world",
                language="en",
                language_probability=0.98,
            )
        )
    )

    module = get_router_module()

    monkeypatch.setattr(
        module,
        "whisper_transcriber",
        fake_transcriber,
    )

    response = client.post(
        "/voice/transcribe",
        files={
            "audio": (
                "test.webm",
                b"fake-webm-audio",
                "audio/webm",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data == {
        "transcript": "hello world",
        "language": "en",
        "language_probability": 0.98,
    }

    assert len(
        fake_transcriber.calls
    ) == 1


# ============================================================
# Test 2
# ============================================================


def test_uploaded_audio_reaches_transcriber(
    client,
    monkeypatch,
):

    fake_transcriber = (
        FakeWhisperTranscriber()
    )

    module = get_router_module()

    monkeypatch.setattr(
        module,
        "whisper_transcriber",
        fake_transcriber,
    )

    audio = (
        b"this-is-fake-webm-audio"
    )

    response = client.post(
        "/voice/transcribe",
        files={
            "audio": (
                "recording.webm",
                audio,
                "audio/webm",
            )
        },
    )

    assert response.status_code == 200

    assert len(
        fake_transcriber.calls
    ) == 1

    temp_path = Path(
        fake_transcriber.calls[0]
    )

    assert temp_path.exists() is False


# ============================================================
# Test 3
# ============================================================


def test_empty_audio_returns_400(
    client,
    monkeypatch,
):

    fake_transcriber = (
        FakeWhisperTranscriber()
    )

    module = get_router_module()

    monkeypatch.setattr(
        module,
        "whisper_transcriber",
        fake_transcriber,
    )

    response = client.post(
        "/voice/transcribe",
        files={
            "audio": (
                "empty.webm",
                b"",
                "audio/webm",
            )
        },
    )

    assert response.status_code == 400

    data = response.json()

    assert data["detail"] == (
        "Uploaded audio is empty."
    )

    assert fake_transcriber.calls == []


# ============================================================
# Test 4
# ============================================================


def test_transcription_failure_returns_500(
    client,
    monkeypatch,
):

    fake_transcriber = (
        FakeWhisperTranscriber(
            error=RuntimeError(
                "whisper failed"
            )
        )
    )

    module = get_router_module()

    monkeypatch.setattr(
        module,
        "whisper_transcriber",
        fake_transcriber,
    )

    response = client.post(
        "/voice/transcribe",
        files={
            "audio": (
                "test.webm",
                b"fake-audio",
                "audio/webm",
            )
        },
    )

    assert response.status_code == 500

    data = response.json()

    assert data["detail"] == (
        "Audio transcription failed."
    )


# ============================================================
# Test 5
# ============================================================


def test_temp_file_is_deleted_after_success(
    client,
    monkeypatch,
):

    captured_path = []

    class TrackingTranscriber:

        async def transcribe(
            self,
            audio_path: str,
        ):

            captured_path.append(
                audio_path
            )

            assert Path(
                audio_path
            ).exists()

            return (
                FakeTranscriptionResult(
                    text="temporary file test"
                )
            )

    module = get_router_module()

    monkeypatch.setattr(
        module,
        "whisper_transcriber",
        TrackingTranscriber(),
    )

    response = client.post(
        "/voice/transcribe",
        files={
            "audio": (
                "test.webm",
                b"fake-audio",
                "audio/webm",
            )
        },
    )

    assert response.status_code == 200

    assert len(
        captured_path
    ) == 1

    assert Path(
        captured_path[0]
    ).exists() is False


# ============================================================
# Test 6
# ============================================================


def test_temp_file_is_deleted_after_failure(
    client,
    monkeypatch,
):

    captured_path = []

    class FailingTranscriber:

        async def transcribe(
            self,
            audio_path: str,
        ):

            captured_path.append(
                audio_path
            )

            assert Path(
                audio_path
            ).exists()

            raise RuntimeError(
                "transcription failed"
            )

    module = get_router_module()

    monkeypatch.setattr(
        module,
        "whisper_transcriber",
        FailingTranscriber(),
    )

    response = client.post(
        "/voice/transcribe",
        files={
            "audio": (
                "test.webm",
                b"fake-audio",
                "audio/webm",
            )
        },
    )

    assert response.status_code == 500

    assert len(
        captured_path
    ) == 1

    assert Path(
        captured_path[0]
    ).exists() is False


# ============================================================
# Test 7
# ============================================================


def test_language_information_is_returned(
    client,
    monkeypatch,
):

    fake_transcriber = (
        FakeWhisperTranscriber(
            result=FakeTranscriptionResult(
                text="namaste",
                language="hi",
                language_probability=0.91,
            )
        )
    )

    module = get_router_module()

    monkeypatch.setattr(
        module,
        "whisper_transcriber",
        fake_transcriber,
    )

    response = client.post(
        "/voice/transcribe",
        files={
            "audio": (
                "hindi.webm",
                b"fake-audio",
                "audio/webm",
            )
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["transcript"] == (
        "namaste"
    )

    assert data["language"] == "hi"

    assert data[
        "language_probability"
    ] == 0.91


# ============================================================
# Test 8
# ============================================================


def test_transcriber_receives_existing_temp_file(
    client,
    monkeypatch,
):

    received_path = []

    class InspectingTranscriber:

        async def transcribe(
            self,
            audio_path: str,
        ):

            path = Path(
                audio_path
            )

            received_path.append(
                path
            )

            assert path.exists()

            assert path.is_file()

            assert path.suffix == (
                ".webm"
            )

            return (
                FakeTranscriptionResult()
            )

    module = get_router_module()

    monkeypatch.setattr(
        module,
        "whisper_transcriber",
        InspectingTranscriber(),
    )

    response = client.post(
        "/voice/transcribe",
        files={
            "audio": (
                "voice.webm",
                b"fake-audio-data",
                "audio/webm",
            )
        },
    )

    assert response.status_code == 200

    assert len(
        received_path
    ) == 1

    assert received_path[
        0
    ].exists() is False


# ============================================================
# Test 9
# ============================================================


def test_multiple_requests_are_independent(
    client,
    monkeypatch,
):

    fake_transcriber = (
        FakeWhisperTranscriber()
    )

    module = get_router_module()

    monkeypatch.setattr(
        module,
        "whisper_transcriber",
        fake_transcriber,
    )

    response_one = client.post(
        "/voice/transcribe",
        files={
            "audio": (
                "one.webm",
                b"audio-one",
                "audio/webm",
            )
        },
    )

    response_two = client.post(
        "/voice/transcribe",
        files={
            "audio": (
                "two.webm",
                b"audio-two",
                "audio/webm",
            )
        },
    )

    assert response_one.status_code == 200
    assert response_two.status_code == 200

    assert len(
        fake_transcriber.calls
    ) == 2

    assert (
        fake_transcriber.calls[0]
        != fake_transcriber.calls[1]
    )


# ============================================================
# Test 10
# ============================================================


def test_missing_audio_field_returns_422(
    client,
    monkeypatch,
):

    fake_transcriber = (
        FakeWhisperTranscriber()
    )

    module = get_router_module()

    monkeypatch.setattr(
        module,
        "whisper_transcriber",
        fake_transcriber,
    )

    response = client.post(
        "/voice/transcribe"
    )

    assert response.status_code == 422

    assert fake_transcriber.calls == []