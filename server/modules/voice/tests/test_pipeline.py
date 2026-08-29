"""
Tests for the voice pipeline orchestration layer.

The pipeline connects:

    WebM/Opus
        ↓
    AudioDecoder
        ↓
    PCM16
        ↓
    VAD
        ↓
    Whisper
        ↓
    TurnDetector
        ↓
    VoiceAssistant
        ↓
    callbacks

These tests intentionally use fake components.

They must NOT:
    - load Faster-Whisper
    - execute LangGraph
    - require WebSocket
    - require real browser audio
    - require a microphone
"""

from __future__ import annotations

import asyncio

import pytest
from modules.voice.models import (
    SpeechStarted,
    TranscriptChanged,
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
    """
    Fake WebM/Opus decoder.

    The pipeline only needs decode() and close().
    """

    def __init__(self, frames=None):
        self.frames = frames or []
        self.decode_calls = []
        self.closed = False

    async def decode(self, audio_chunk: bytes) -> list[bytes]:
        self.decode_calls.append(audio_chunk)
        return list(self.frames)

    async def close(self) -> None:
        self.closed = True


class FakeVAD:
    """
    Fake VAD.

    Every call to process() returns the configured events.
    """

    def __init__(self, events=None):
        self.events = events or []
        self.process_calls = []
        self.reset_called = False

    def process(self, frame: bytes) -> list[VADEvent]:
        self.process_calls.append(frame)
        return list(self.events)

    def reset(self) -> None:
        self.reset_called = True


class FakeTranscriber:
    """
    Fake Whisper transcriber.

    No actual model is loaded.
    """

    def __init__(
        self,
        text: str = "hello world",
        has_speech: bool = True,
    ):
        self.text = text
        self.has_speech = has_speech

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

        return TranscriptionResult(
            text=self.text,
            has_speech=self.has_speech,
            language="en",
            language_probability=0.99,
            speech_probability=0.99,
        )


class FakeTurnDetector:
    """
    Fake turn detector.

    The pipeline only cares about the events returned by
    process().
    """

    def __init__(self, events=None):
        self.events = events or []

        self.process_calls = []

        self.reset_called = False

    async def process(
        self,
        transcript: str,
    ) -> list:

        self.process_calls.append(
            transcript
        )

        return list(self.events)

    async def reset(self) -> None:
        self.reset_called = True


class FakeAssistant:
    """
    Fake assistant.

    It behaves like the real assistant from the pipeline's
    perspective.
    """

    def __init__(
        self,
        response: str = "Hello from assistant.",
    ):
        self.response = response

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

        return self.response

    def cancel(self) -> None:
        self.cancel_calls += 1


# ============================================================
# Helpers
# ============================================================


def create_pipeline(
    *,
    decoder=None,
    vad=None,
    transcriber=None,
    turn_detector=None,
    assistant=None,
    **callbacks,
):
    """
    Create a pipeline entirely from fake dependencies.
    """

    return VoicePipeline(
        session_id="test-session",
        decoder=decoder or FakeDecoder(),
        vad=vad or FakeVAD(),
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


# ============================================================
# Lifecycle
# ============================================================


@pytest.mark.anyio
async def test_pipeline_starts():

    pipeline = create_pipeline()

    assert pipeline.running is False

    await pipeline.start()

    assert pipeline.running is True

    await pipeline.close()


@pytest.mark.anyio
async def test_pipeline_start_is_idempotent():

    pipeline = create_pipeline()

    await pipeline.start()
    await pipeline.start()

    assert pipeline.running is True

    await pipeline.close()


@pytest.mark.anyio
async def test_pipeline_close_is_idempotent():

    decoder = FakeDecoder()

    pipeline = create_pipeline(
        decoder=decoder,
    )

    await pipeline.start()

    await pipeline.close()
    await pipeline.close()

    assert pipeline.running is False
    assert decoder.closed is True


@pytest.mark.anyio
async def test_receive_audio_before_start_is_ignored():

    decoder = FakeDecoder()

    pipeline = create_pipeline(
        decoder=decoder,
    )

    await pipeline.receive_audio(
        b"audio"
    )

    assert decoder.decode_calls == []


@pytest.mark.anyio
async def test_empty_audio_is_ignored():

    decoder = FakeDecoder()

    pipeline = create_pipeline(
        decoder=decoder,
    )

    await pipeline.start()

    await pipeline.receive_audio(
        b""
    )

    assert decoder.decode_calls == []

    await pipeline.close()


# ============================================================
# Audio → Decoder → VAD
# ============================================================


@pytest.mark.anyio
async def test_receive_audio_passes_audio_to_decoder():

    decoder = FakeDecoder(
        frames=[
            b"pcm-frame",
        ]
    )

    vad = FakeVAD()

    pipeline = create_pipeline(
        decoder=decoder,
        vad=vad,
    )

    await pipeline.start()

    await pipeline.receive_audio(
        b"webm-audio"
    )

    assert decoder.decode_calls == [
        b"webm-audio"
    ]

    assert vad.process_calls == [
        b"pcm-frame"
    ]

    await pipeline.close()


@pytest.mark.anyio
async def test_multiple_decoded_frames_are_sent_to_vad():

    decoder = FakeDecoder(
        frames=[
            b"frame-1",
            b"frame-2",
            b"frame-3",
        ]
    )

    vad = FakeVAD()

    pipeline = create_pipeline(
        decoder=decoder,
        vad=vad,
    )

    await pipeline.start()

    await pipeline.receive_audio(
        b"audio"
    )

    assert vad.process_calls == [
        b"frame-1",
        b"frame-2",
        b"frame-3",
    ]

    await pipeline.close()


# ============================================================
# VAD
# ============================================================


@pytest.mark.anyio
async def test_speech_started_interrupts_assistant():

    event = VADEvent(
        type=VADEventType.SPEECH_STARTED,
        speech_duration=0.5,
        audio=b"speech",
    )

    vad = FakeVAD(
        events=[event]
    )

    assistant = FakeAssistant()

    pipeline = create_pipeline(
        decoder=FakeDecoder(
            frames=[b"pcm-frame"]
        ),
        vad=vad,
        assistant=assistant,
    )

    await pipeline.start()

    pipeline.assistant_turn_id = 1

    await pipeline.receive_audio(
        b"audio"
    )

    assert assistant.cancel_calls == 1

    await pipeline.close()


@pytest.mark.anyio
async def test_speech_end_without_audio_is_ignored():

    event = VADEvent(
        type=VADEventType.SPEECH_ENDED,
        speech_duration=1.0,
        audio=b"",
    )

    vad = FakeVAD(
        events=[event]
    )

    transcriber = FakeTranscriber()

    pipeline = create_pipeline(
        vad=vad,
        transcriber=transcriber,
    )

    await pipeline.start()

    await pipeline.receive_audio(
        b"audio"
    )

    await asyncio.sleep(0)

    assert transcriber.calls == []

    await pipeline.close()


@pytest.mark.anyio
async def test_short_speech_is_ignored():

    event = VADEvent(
        type=VADEventType.SPEECH_ENDED,
        speech_duration=0.001,
        audio=b"speech",
    )

    vad = FakeVAD(
        events=[event]
    )

    transcriber = FakeTranscriber()

    pipeline = create_pipeline(
        vad=vad,
        transcriber=transcriber,
    )

    await pipeline.start()

    await pipeline.receive_audio(
        b"audio"
    )

    await asyncio.sleep(0)

    assert transcriber.calls == []

    await pipeline.close()


# ============================================================
# Speech → Whisper
# ============================================================


@pytest.mark.anyio
async def test_speech_is_sent_to_transcriber():

    transcriber = FakeTranscriber(
        text="hello world"
    )

    pipeline = create_pipeline(
        transcriber=transcriber,
    )

    await pipeline.start()

    await pipeline._transcribe_speech(
        b"pcm-speech",
        pipeline.generation,
    )

    assert len(
        transcriber.calls
    ) == 1

    audio, sample_rate = (
        transcriber.calls[0]
    )

    assert audio == b"pcm-speech"
    assert sample_rate == 16000

    await pipeline.close()


@pytest.mark.anyio
async def test_transcription_without_speech_is_ignored():

    transcriber = FakeTranscriber(
        text="",
        has_speech=False,
    )

    turn_detector = FakeTurnDetector()

    pipeline = create_pipeline(
        transcriber=transcriber,
        turn_detector=turn_detector,
    )

    await pipeline.start()

    await pipeline._transcribe_speech(
        b"pcm-speech",
        pipeline.generation,
    )

    assert (
        turn_detector.process_calls
        == []
    )

    await pipeline.close()


@pytest.mark.anyio
async def test_empty_transcript_is_ignored():

    transcriber = FakeTranscriber(
        text="   ",
        has_speech=True,
    )

    turn_detector = FakeTurnDetector()

    pipeline = create_pipeline(
        transcriber=transcriber,
        turn_detector=turn_detector,
    )

    await pipeline.start()

    await pipeline._transcribe_speech(
        b"pcm-speech",
        pipeline.generation,
    )

    assert (
        turn_detector.process_calls
        == []
    )

    await pipeline.close()


# ============================================================
# Transcript → TurnDetector
# ============================================================


@pytest.mark.anyio
async def test_transcript_is_sent_to_turn_detector():

    turn_detector = FakeTurnDetector()

    pipeline = create_pipeline(
        turn_detector=turn_detector,
    )

    await pipeline.start()

    await pipeline._process_transcript(
        "hello world"
    )

    assert (
        turn_detector.process_calls
        == ["hello world"]
    )

    await pipeline.close()


@pytest.mark.anyio
async def test_speech_started_callback_is_emitted():

    received = []

    async def on_speech_started(
        event: SpeechStarted,
    ) -> None:

        received.append(event)

    turn_detector = FakeTurnDetector(
        events=[
            SpeechStarted(
                turn_id=1
            )
        ]
    )

    pipeline = create_pipeline(
        turn_detector=turn_detector,
        on_speech_started=(
            on_speech_started
        ),
    )

    await pipeline.start()

    await pipeline._process_transcript(
        "hello"
    )

    assert len(received) == 1

    assert received[0].turn_id == 1

    await pipeline.close()


@pytest.mark.anyio
async def test_transcript_changed_callback_is_emitted():

    received = []

    async def on_transcript_changed(
        event: TranscriptChanged,
    ) -> None:

        received.append(event)

    turn_detector = FakeTurnDetector(
        events=[
            TranscriptChanged(
                turn_id=1,
                text="hello",
            )
        ]
    )

    pipeline = create_pipeline(
        turn_detector=turn_detector,
        on_transcript_changed=(
            on_transcript_changed
        ),
    )

    await pipeline.start()

    await pipeline._process_transcript(
        "hello"
    )

    assert len(received) == 1

    assert received[0].turn_id == 1
    assert received[0].text == "hello"

    await pipeline.close()


# ============================================================
# Turn completion
# ============================================================


@pytest.mark.anyio
async def test_turn_completion_callback_is_emitted():

    received = []

    async def on_turn_complete(
        event: TurnCompleted,
    ) -> None:

        received.append(event)

    assistant = FakeAssistant()

    pipeline = create_pipeline(
        assistant=assistant,
        on_turn_complete=(
            on_turn_complete
        ),
    )

    await pipeline.start()

    completed = TurnCompleted(
        turn_id=1,
        text="What is AI?",
    )

    await pipeline._handle_turn_complete(
        completed
    )

    assert len(received) == 1

    assert received[0].turn_id == 1
    assert received[0].text == "What is AI?"

    await pipeline.close()


# ============================================================
# Assistant
# ============================================================


@pytest.mark.anyio
async def test_completed_turn_starts_assistant():

    assistant = FakeAssistant(
        response="AI is artificial intelligence."
    )

    started = []
    responses = []
    completed = []

    async def on_assistant_started(
        turn_id: int,
    ) -> None:

        started.append(turn_id)

    async def on_assistant_text(
        text: str,
        turn_id: int,
    ) -> None:

        responses.append(
            (
                text,
                turn_id,
            )
        )

    async def on_assistant_completed(
        turn_id: int,
    ) -> None:

        completed.append(turn_id)

    pipeline = create_pipeline(
        assistant=assistant,
        on_assistant_started=(
            on_assistant_started
        ),
        on_assistant_text=(
            on_assistant_text
        ),
        on_assistant_completed=(
            on_assistant_completed
        ),
    )

    await pipeline.start()

    await pipeline._start_assistant(
        "What is AI?",
        1,
    )

    assert assistant.calls == [
        (
            "What is AI?",
            "test-session",
        )
    ]

    assert started == [1]

    assert responses == [
        (
            "AI is artificial intelligence.",
            1,
        )
    ]

    assert completed == [1]

    assert (
        pipeline.assistant_turn_id
        is None
    )

    await pipeline.close()


@pytest.mark.anyio
async def test_assistant_error_callback_is_emitted():

    class FailingAssistant:
        def __init__(self):
            self.cancel_calls = 0

        async def start(
            self,
            text: str,
            session_id: str,
        ):
            raise RuntimeError(
                "assistant failed"
            )

        def cancel(self):
            self.cancel_calls += 1

    errors = []

    async def on_assistant_error(
        turn_id: int,
        error: Exception,
    ) -> None:

        errors.append(
            (
                turn_id,
                error,
            )
        )

    assistant = FailingAssistant()

    pipeline = create_pipeline(
        assistant=assistant,
        on_assistant_error=(
            on_assistant_error
        ),
    )

    await pipeline.start()

    await pipeline._start_assistant(
        "hello",
        1,
    )

    assert len(errors) == 1

    assert errors[0][0] == 1

    assert isinstance(
        errors[0][1],
        RuntimeError,
    )

    await pipeline.close()


# ============================================================
# Interruption
# ============================================================


@pytest.mark.anyio
async def test_interrupt_assistant_clears_assistant_state():

    assistant = FakeAssistant()

    pipeline = create_pipeline(
        assistant=assistant,
    )

    await pipeline.start()

    pipeline.assistant_turn_id = 5

    await pipeline.interrupt_assistant()

    assert (
        pipeline.assistant_turn_id
        is None
    )

    assert assistant.cancel_calls == 1

    await pipeline.close()


@pytest.mark.anyio
async def test_interrupt_without_active_assistant_is_safe():

    assistant = FakeAssistant()

    pipeline = create_pipeline(
        assistant=assistant,
    )

    await pipeline.start()

    await pipeline.interrupt_assistant()

    assert assistant.cancel_calls == 0

    await pipeline.close()


# ============================================================
# Generation / stale work
# ============================================================


@pytest.mark.anyio
async def test_stale_transcription_is_ignored():

    transcriber = FakeTranscriber(
        text="hello"
    )

    turn_detector = FakeTurnDetector()

    pipeline = create_pipeline(
        transcriber=transcriber,
        turn_detector=turn_detector,
    )

    await pipeline.start()

    stale_generation = pipeline.generation

    pipeline.generation += 1

    await pipeline._transcribe_speech(
        b"speech",
        stale_generation,
    )

    assert (
        turn_detector.process_calls
        == []
    )

    await pipeline.close()


# ============================================================
# Close cleanup
# ============================================================


@pytest.mark.anyio
async def test_close_resets_components():

    decoder = FakeDecoder()

    vad = FakeVAD()

    turn_detector = FakeTurnDetector()

    pipeline = create_pipeline(
        decoder=decoder,
        vad=vad,
        turn_detector=turn_detector,
    )

    await pipeline.start()

    await pipeline.close()

    assert pipeline.running is False

    assert decoder.closed is True

    assert vad.reset_called is True

    assert (
        turn_detector.reset_called
        is True
    )


@pytest.mark.anyio
async def test_receive_audio_after_close_is_ignored():

    decoder = FakeDecoder()

    pipeline = create_pipeline(
        decoder=decoder,
    )

    await pipeline.start()

    await pipeline.close()

    await pipeline.receive_audio(
        b"audio"
    )

    assert decoder.decode_calls == []