"""
Unit tests for the Voice WebSocket API.

These tests isolate the WebSocket router from the real voice
pipeline and Whisper implementation.

They verify:

    - WebSocket connection
    - connected event
    - start_session command
    - binary audio forwarding
    - ping/pong
    - invalid JSON handling
    - unknown message handling
    - close_session
    - client disconnect
    - session cleanup
"""

from __future__ import annotations

import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.voice_ws_router import router


# ============================================================
# Fake VoiceSession
# ============================================================


class FakeVoiceSession:
    """
    Deterministic fake VoiceSession used to isolate the router.
    """

    instances = []

    def __init__(
        self,
        websocket,
        session_id: str,
    ):
        self.websocket = websocket
        self.session_id = session_id
        self.running = True

        self.sent_events = []
        self.received_audio = []
        self.start_calls = 0
        self.close_calls = 0

        FakeVoiceSession.instances.append(self)

    async def send(self, event):
        self.sent_events.append(event)

        await self.websocket.send_json(event)

    async def receive_audio(
        self,
        audio_chunk: bytes,
    ):
        self.received_audio.append(
            audio_chunk
        )

    async def start(self):
        self.start_calls += 1

    async def close(self):
        self.close_calls += 1
        self.running = False


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture(autouse=True)
def reset_fake_sessions():

    FakeVoiceSession.instances.clear()

    yield

    FakeVoiceSession.instances.clear()


@pytest.fixture
def app(monkeypatch):

    monkeypatch.setattr(
        "api.voice_ws_router.VoiceSession",
        FakeVoiceSession,
    )

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


def get_session():

    assert len(
        FakeVoiceSession.instances
    ) == 1

    return FakeVoiceSession.instances[0]


# ============================================================
# Test 1
# ============================================================


def test_websocket_connection_sends_connected_event(
    client,
):

    with client.websocket_connect(
        "/voice/ws/test-session"
    ) as websocket:

        event = websocket.receive_json()

        assert event["type"] == "connected"

        session = get_session()

        assert (
            session.session_id
            == "test-session"
        )


# ============================================================
# Test 2
# ============================================================


def test_start_session_calls_session_start(
    client,
):

    with client.websocket_connect(
        "/voice/ws/session-123"
    ) as websocket:

        # connected event
        websocket.receive_json()

        websocket.send_json(
            {
                "type": "start_session"
            }
        )

        session = get_session()

        assert (
            session.start_calls
            == 1
        )


# ============================================================
# Test 3
# ============================================================


def test_binary_audio_reaches_session(
    client,
):

    audio = (
        b"\x01\x02\x03\x04"
        b"\x05\x06\x07\x08"
    )

    with client.websocket_connect(
        "/voice/ws/audio-session"
    ) as websocket:

        websocket.receive_json()

        websocket.send_bytes(
            audio
        )

        session = get_session()

        assert (
            session.received_audio
            == [audio]
        )


# ============================================================
# Test 4
# ============================================================


def test_multiple_audio_chunks_reach_session(
    client,
):

    audio_one = b"audio-one"
    audio_two = b"audio-two"
    audio_three = b"audio-three"

    with client.websocket_connect(
        "/voice/ws/audio-session"
    ) as websocket:

        websocket.receive_json()

        websocket.send_bytes(
            audio_one
        )

        websocket.send_bytes(
            audio_two
        )

        websocket.send_bytes(
            audio_three
        )

        session = get_session()

        assert (
            session.received_audio
            == [
                audio_one,
                audio_two,
                audio_three,
            ]
        )


# ============================================================
# Test 5
# ============================================================


def test_ping_returns_pong(
    client,
):

    with client.websocket_connect(
        "/voice/ws/ping-session"
    ) as websocket:

        websocket.receive_json()

        websocket.send_json(
            {
                "type": "ping"
            }
        )

        response = (
            websocket.receive_json()
        )

        assert response == {
            "type": "pong"
        }


# ============================================================
# Test 6
# ============================================================


def test_invalid_json_returns_error(
    client,
):

    with client.websocket_connect(
        "/voice/ws/json-session"
    ) as websocket:

        websocket.receive_json()

        websocket.send_text(
            "{invalid json"
        )

        response = (
            websocket.receive_json()
        )

        assert response["type"] == "error"

        assert (
            response["code"]
            == "INVALID_JSON"
        )

        assert (
            response["message"]
            == "Invalid JSON."
        )


# ============================================================
# Test 7
# ============================================================


def test_unknown_message_type_returns_error(
    client,
):

    with client.websocket_connect(
        "/voice/ws/unknown-session"
    ) as websocket:

        websocket.receive_json()

        websocket.send_json(
            {
                "type": "something_unknown"
            }
        )

        response = (
            websocket.receive_json()
        )

        assert response["type"] == "error"

        assert (
            response["code"]
            == "UNKNOWN_MESSAGE_TYPE"
        )

        assert (
            "something_unknown"
            in response["message"]
        )


# ============================================================
# Test 8
# ============================================================


def test_missing_message_type_returns_error(
    client,
):

    with client.websocket_connect(
        "/voice/ws/missing-type-session"
    ) as websocket:

        websocket.receive_json()

        websocket.send_json(
            {
                "foo": "bar"
            }
        )

        response = (
            websocket.receive_json()
        )

        assert response["type"] == "error"

        assert (
            response["code"]
            == "UNKNOWN_MESSAGE_TYPE"
        )


# ============================================================
# Test 9
# ============================================================


def test_close_session_closes_voice_session(
    client,
):

    with client.websocket_connect(
        "/voice/ws/close-session"
    ) as websocket:

        websocket.receive_json()

        websocket.send_json(
            {
                "type": "close_session"
            }
        )

        session = get_session()

        assert (
            session.close_calls
            == 1
        )

        assert (
            session.running
            is False
        )


# ============================================================
# Test 10
# ============================================================


def test_session_is_closed_when_client_disconnects(
    client,
):

    with client.websocket_connect(
        "/voice/ws/disconnect-session"
    ) as websocket:

        websocket.receive_json()

    session = get_session()

    assert (
        session.close_calls
        == 1
    )

    assert (
        session.running
        is False
    )


# ============================================================
# Test 11
# ============================================================


def test_session_receives_correct_session_id(
    client,
):

    session_id = (
        "user-123-session-456"
    )

    with client.websocket_connect(
        f"/voice/ws/{session_id}"
    ) as websocket:

        websocket.receive_json()

        session = get_session()

        assert (
            session.session_id
            == session_id
        )


# ============================================================
# Test 12
# ============================================================


def test_start_session_does_not_send_extra_response(
    client,
):

    with client.websocket_connect(
        "/voice/ws/start-session"
    ) as websocket:

        connected = (
            websocket.receive_json()
        )

        assert (
            connected["type"]
            == "connected"
        )

        websocket.send_json(
            {
                "type": "start_session"
            }
        )

        session = get_session()

        assert (
            session.start_calls
            == 1
        )

        assert (
            len(
                session.sent_events
            )
            == 1
        )


# ============================================================
# Test 13
# ============================================================


def test_audio_and_commands_can_be_interleaved(
    client,
):

    audio_one = b"first"
    audio_two = b"second"

    with client.websocket_connect(
        "/voice/ws/interleaved-session"
    ) as websocket:

        websocket.receive_json()

        websocket.send_json(
            {
                "type": "start_session"
            }
        )

        websocket.send_bytes(
            audio_one
        )

        websocket.send_json(
            {
                "type": "ping"
            }
        )

        pong = (
            websocket.receive_json()
        )

        assert pong == {
            "type": "pong"
        }

        websocket.send_bytes(
            audio_two
        )

        session = get_session()

        assert (
            session.start_calls
            == 1
        )

        assert (
            session.received_audio
            == [
                audio_one,
                audio_two,
            ]
        )


# ============================================================
# Test 14
# ============================================================


def test_empty_binary_audio_is_forwarded(
    client,
):

    with client.websocket_connect(
        "/voice/ws/empty-audio-session"
    ) as websocket:

        websocket.receive_json()

        websocket.send_bytes(
            b""
        )

        session = get_session()

        assert (
            session.received_audio
            == [b""]
        )


# ============================================================
# Test 15
# ============================================================


def test_multiple_start_commands_are_forwarded(
    client,
):

    with client.websocket_connect(
        "/voice/ws/multiple-start-session"
    ) as websocket:

        websocket.receive_json()

        websocket.send_json(
            {
                "type": "start_session"
            }
        )

        websocket.send_json(
            {
                "type": "start_session"
            }
        )

        session = get_session()

        assert (
            session.start_calls
            == 2
        )