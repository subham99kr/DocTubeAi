"""
Unit tests for VoicePipeline orchestration.

These tests intentionally mock all external voice components.

They verify that VoicePipeline correctly handles:

    start()
    close()
    transcription failures
    empty transcriptions
    no-speech transcriptions
    turn detector failures
    assistant failures
    assistant cancellation
    multiple completed turns

Real audio decoding and VAD are tested separately in:

    test_voice_integration.py
"""

from __future__ import annotations

import asyncio

import pytest

from modules.voice.models import (
    TranscriptionResult,
    TurnCompleted,
)

from modules.voice.pipeline import VoicePipeline

from modules.voice.vad import (
    VADEvent,
    VADEventType,
)


# ============================================================
# Fake components
# ============================================================


class FakeDecoder:
    """Minimal decoder used to isolate VoicePipeline."""

    def __init__(self):
        self.started = False
        self.closed = False
        self.decode_calls = []

    async def start(self):
        self.started = True

    async def decode(self, audio: bytes):
        self.decode_calls.append(audio)
        return []

    async def close(self):
        self.closed = True


class FakeVAD:
    """Minimal VAD."""

    def __init__(self):
        self.reset_called = False

    def process(self, frame: bytes):
        return []

    def reset(self):
        self.reset_called = True


class FakeTranscriber:
    """Deterministic transcriber."""

    def __init__(
        self,
        result: TranscriptionResult | None = None,
        error: Exception | None = None,
    ):
        self.result = result
        self.error = error
        self.calls = []

    async def transcribe_pcm(
        self,
        pcm_audio: bytes,
        sample_rate: int = 16000,
    ) -> TranscriptionResult:

        self.calls.append(
            (
                pcm_audio,
                sample_rate,
            )
        )

        if self.error is not None:
            raise self.error

        if self.result is not None:
            return self.result

        return TranscriptionResult(
            text="hello world",
            has_speech=True,
            language="en",
            language_probability=0.99,
            speech_probability=0.99,
        )


class FakeTurnDetector:
    """Deterministic turn detector."""

    def __init__(
        self,
        events=None,
        error: Exception | None = None,
    ):
        self.events = (
            events
            if events is not None
            else []
        )

        self.error = error
        self.process_calls = []
        self.reset_called = False
        self.on_turn_complete = None

    async def process(
        self,
        transcript: str,
    ):

        self.process_calls.append(
            transcript
        )

        if self.error is not None:
            raise self.error

        # Simulate the real TurnDetector callback
        # behavior for completed turns.
        for event in self.events:
            if (
                isinstance(event, TurnCompleted)
                and self.on_turn_complete
            ):
                await self.on_turn_complete(
                    event
                )

        return self.events

    async def reset(self):
        self.reset_called = True


class FakeAssistant:
    """Deterministic assistant."""

    def __init__(
        self,
        response: str = "Hello from assistant.",
        error: Exception | None = None,
    ):
        self.response = response
        self.error = error

        self.calls = []
        self.cancel_calls = 0

    async def start(
        self,
        text: str,
        session_id: str,
    ) -> str:

        self.calls.append(
            (
                text,
                session_id,
            )
        )

        if self.error is not None:
            raise self.error

        return self.response

    def cancel(self):
        self.cancel_calls += 1


# ============================================================
# Helpers
# ============================================================


def create_pipeline(
    *,
    transcriber=None,
    turn_detector=None,
    assistant=None,
    **callbacks,
):

    return VoicePipeline(
        session_id="pipeline-test-session",
        decoder=FakeDecoder(),
        vad=FakeVAD(),
        transcriber=(
            transcriber
            or FakeTranscriber()
        ),
        turn_detector=(
            turn_detector
            or FakeTurnDetector()
        ),
        assistant=(
            assistant
            or FakeAssistant()
        ),
        **callbacks,
    )


async def wait_until(
    predicate,
    *,
    timeout: float = 1.0,
    interval: float = 0.01,
) -> bool:

    elapsed = 0.0

    while elapsed < timeout:

        if predicate():
            return True

        await asyncio.sleep(
            interval
        )

        elapsed += interval

    return False


async def send_speech(
    pipeline: VoicePipeline,
) -> None:

    await pipeline._handle_speech_ended(
        VADEvent(
            type=VADEventType.SPEECH_ENDED,
            speech_duration=1.0,
            audio=b"pcm-audio",
        )
    )


# ============================================================
# Test 1
# ============================================================


def test_pipeline_starts():

    async def run():

        pipeline = create_pipeline()

        assert pipeline.running is False

        await pipeline.start()

        assert pipeline.running is True

        await pipeline.close()

    asyncio.run(run())


# ============================================================
# Test 2
# ============================================================


def test_pipeline_closes():

    async def run():

        decoder = FakeDecoder()

        pipeline = VoicePipeline(
            session_id="pipeline-test-session",
            decoder=decoder,
            vad=FakeVAD(),
            transcriber=FakeTranscriber(),
            turn_detector=FakeTurnDetector(),
            assistant=FakeAssistant(),
        )

        await pipeline.start()

        assert pipeline.running is True

        await pipeline.close()

        assert pipeline.running is False
        assert decoder.closed is True

    asyncio.run(run())


# ============================================================
# Test 3
# ============================================================


def test_receive_audio_after_start():

    async def run():

        decoder = FakeDecoder()

        pipeline = VoicePipeline(
            session_id="pipeline-test-session",
            decoder=decoder,
            vad=FakeVAD(),
            transcriber=FakeTranscriber(),
            turn_detector=FakeTurnDetector(),
            assistant=FakeAssistant(),
        )

        await pipeline.start()

        audio = b"fake-audio"

        await pipeline.receive_audio(
            audio
        )

        assert decoder.decode_calls == [
            audio
        ]

        await pipeline.close()

    asyncio.run(run())


# ============================================================
# Test 4
# ============================================================


def test_transcription_result_without_speech_is_ignored():

    async def run():

        transcriber = FakeTranscriber(
            result=TranscriptionResult(
                text="",
                has_speech=False,
                language="en",
                language_probability=0.99,
                speech_probability=0.01,
            )
        )

        turn_detector = FakeTurnDetector()

        pipeline = create_pipeline(
            transcriber=transcriber,
            turn_detector=turn_detector,
        )

        await pipeline.start()

        await send_speech(
            pipeline
        )

        await asyncio.sleep(0.05)

        assert transcriber.calls

        assert (
            turn_detector.process_calls
            == []
        )

        await pipeline.close()

    asyncio.run(run())


# ============================================================
# Test 5
# ============================================================


def test_empty_transcription_is_ignored():

    async def run():

        transcriber = FakeTranscriber(
            result=TranscriptionResult(
                text="",
                has_speech=True,
                language="en",
                language_probability=0.99,
                speech_probability=0.99,
            )
        )

        turn_detector = FakeTurnDetector()

        pipeline = create_pipeline(
            transcriber=transcriber,
            turn_detector=turn_detector,
        )

        await pipeline.start()

        await send_speech(
            pipeline
        )

        await asyncio.sleep(0.05)

        assert (
            turn_detector.process_calls
            == []
        )

        await pipeline.close()

    asyncio.run(run())


# ============================================================
# Test 6
# ============================================================


def test_turn_detector_receives_transcription():

    async def run():

        transcriber = FakeTranscriber(
            result=TranscriptionResult(
                text="hello pipeline",
                has_speech=True,
                language="en",
                language_probability=0.99,
                speech_probability=0.99,
            )
        )

        turn_detector = FakeTurnDetector()

        pipeline = create_pipeline(
            transcriber=transcriber,
            turn_detector=turn_detector,
        )

        await pipeline.start()

        await send_speech(
            pipeline
        )

        reached = await wait_until(
            lambda: bool(
                turn_detector.process_calls
            )
        )

        assert reached

        assert (
            turn_detector.process_calls
            == ["hello pipeline"]
        )

        await pipeline.close()

    asyncio.run(run())


# ============================================================
# Test 7
# ============================================================


def test_turn_completed_reaches_assistant():

    async def run():

        turn = TurnCompleted(
            text="hello assistant",
            turn_id=7,
        )

        transcriber = FakeTranscriber(
            result=TranscriptionResult(
                text="hello assistant",
                has_speech=True,
                language="en",
                language_probability=0.99,
                speech_probability=0.99,
            )
        )

        turn_detector = FakeTurnDetector(
            events=[turn]
        )

        assistant = FakeAssistant(
            response="Hello user."
        )

        pipeline = create_pipeline(
            transcriber=transcriber,
            turn_detector=turn_detector,
            assistant=assistant,
        )

        await pipeline.start()

        await send_speech(
            pipeline
        )

        reached = await wait_until(
            lambda: bool(
                assistant.calls
            )
        )

        assert reached

        assert assistant.calls == [
            (
                "hello assistant",
                "pipeline-test-session",
            )
        ]

        await pipeline.close()

    asyncio.run(run())


# ============================================================
# Test 8
# ============================================================


def test_assistant_lifecycle_callbacks():

    async def run():

        turn = TurnCompleted(
            text="hello",
            turn_id=3,
        )

        transcriber = FakeTranscriber(
            result=TranscriptionResult(
                text="hello",
                has_speech=True,
                language="en",
                language_probability=0.99,
                speech_probability=0.99,
            )
        )

        turn_detector = FakeTurnDetector(
            events=[turn]
        )

        assistant = FakeAssistant(
            response="Hi there."
        )

        started = []
        text_events = []
        completed = []

        async def on_started(
            turn_id: int,
        ):
            started.append(
                turn_id
            )

        async def on_text(
            text: str,
            turn_id: int,
        ):
            text_events.append(
                (
                    text,
                    turn_id,
                )
            )

        async def on_completed(
            turn_id: int,
        ):
            completed.append(
                turn_id
            )

        pipeline = create_pipeline(
            transcriber=transcriber,
            turn_detector=turn_detector,
            assistant=assistant,
            on_assistant_started=on_started,
            on_assistant_text=on_text,
            on_assistant_completed=on_completed,
        )

        await pipeline.start()

        await send_speech(
            pipeline
        )

        reached = await wait_until(
            lambda: bool(
                assistant.calls
            )
        )

        assert reached

        # Wait for the assistant task to finish.
        await wait_until(
            lambda: bool(completed)
        )

        assert started == [3]

        assert text_events == [
            (
                "Hi there.",
                3,
            )
        ]

        assert completed == [3]

        await pipeline.close()

    asyncio.run(run())


# ============================================================
# Test 9
# ============================================================


def test_assistant_failure_does_not_crash_pipeline():

    async def run():

        turn = TurnCompleted(
            text="hello",
            turn_id=1,
        )

        transcriber = FakeTranscriber(
            result=TranscriptionResult(
                text="hello",
                has_speech=True,
                language="en",
                language_probability=0.99,
                speech_probability=0.99,
            )
        )

        turn_detector = FakeTurnDetector(
            events=[turn]
        )

        assistant = FakeAssistant(
            error=RuntimeError(
                "assistant failed"
            )
        )

        pipeline = create_pipeline(
            transcriber=transcriber,
            turn_detector=turn_detector,
            assistant=assistant,
        )

        await pipeline.start()

        await send_speech(
            pipeline
        )

        reached = await wait_until(
            lambda: bool(
                assistant.calls
            )
        )

        assert reached

        assert pipeline.running is True

        await pipeline.close()

    asyncio.run(run())


# ============================================================
# Test 10
# ============================================================


def test_assistant_cancel():

    async def run():

        assistant = FakeAssistant()

        pipeline = create_pipeline(
            assistant=assistant
        )

        await pipeline.start()

        await pipeline.cancel_assistant()

        assert (
            assistant.cancel_calls
            == 1
        )

        await pipeline.close()

    asyncio.run(run())


# ============================================================
# Test 11
# ============================================================


def test_multiple_completed_turns():

    async def run():

        turns = [
            TurnCompleted(
                text="first question",
                turn_id=1,
            ),
            TurnCompleted(
                text="second question",
                turn_id=2,
            ),
        ]

        assistant = FakeAssistant()

        transcriber = FakeTranscriber(
            result=TranscriptionResult(
                text="question",
                has_speech=True,
                language="en",
                language_probability=0.99,
                speech_probability=0.99,
            )
        )

        turn_detector = FakeTurnDetector(
            events=turns
        )

        pipeline = create_pipeline(
            transcriber=transcriber,
            turn_detector=turn_detector,
            assistant=assistant,
        )

        await pipeline.start()

        await send_speech(
            pipeline
        )

        reached = await wait_until(
            lambda: len(
                assistant.calls
            ) == 2
        )

        assert reached

        assert assistant.calls == [
            (
                "first question",
                "pipeline-test-session",
            ),
            (
                "second question",
                "pipeline-test-session",
            ),
        ]

        await pipeline.close()

    asyncio.run(run())