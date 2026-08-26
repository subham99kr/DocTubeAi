"""
Integration tests for the voice pipeline.

These tests verify that the real audio components work together:

    WebM/Opus
        ↓
    AudioDecoder
        ↓
    PCM16 frames
        ↓
    VoiceActivityDetector
        ↓
    speech segment
        ↓
    FakeTranscriber
        ↓
    FakeTurnDetector
        ↓
    TurnCompleted
        ↓
    FakeAssistant

These tests intentionally do NOT:

    - load Faster-Whisper
    - execute LangGraph
    - require WebSocket
    - require a browser
    - require a microphone

Only the audio decoding and VAD layers are real.
"""

from __future__ import annotations

import asyncio
import io

import av
import numpy as np
import pytest

from modules.voice.audio_decoder import AudioDecoder
from modules.voice.models import (
    TranscriptionResult,
    TurnCompleted,
)
from modules.voice.pipeline import VoicePipeline
from modules.voice.vad import (
    VADEventType,
    create_vad,
)


# ============================================================
# Constants
# ============================================================

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 20

SAMPLES_PER_FRAME = (
    SAMPLE_RATE
    * FRAME_DURATION_MS
    // 1000
)

# The real VAD needs trailing silence before
# it emits SPEECH_ENDED.
TRAILING_SILENCE_SECONDS = 0.8


# ============================================================
# Fake components
# ============================================================


class FakeTranscriber:
    """
    Fake Whisper transcriber.

    Records every transcription request and returns a
    deterministic transcription result.
    """

    def __init__(
        self,
        text: str = "hello world",
        has_speech: bool = True,
    ) -> None:

        self.text = text
        self.has_speech = has_speech

        self.calls: list[
            tuple[bytes, int]
        ] = []

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

    Records transcripts received from the pipeline
    without completing the turn.
    """

    def __init__(self) -> None:

        self.process_calls: list[str] = []
        self.reset_called = False

    async def process(
        self,
        transcript: str,
    ) -> list:

        self.process_calls.append(
            transcript
        )

        return []

    async def reset(self) -> None:

        self.reset_called = True


class CompletingFakeTurnDetector:
    """
    Fake turn detector that completes a turn.

    Matches the callback-based contract used by VoicePipeline.
    """

    def __init__(self):
        self.process_calls = []
        self.reset_called = False
        self.turn_id = 1

        self.on_turn_complete = None

    async def process(
        self,
        transcript: str,
    ) -> list:

        self.process_calls.append(
            transcript
        )

        event = TurnCompleted(
            text=transcript,
            turn_id=self.turn_id,
        )

        # VoicePipeline may register the callback during
        # initialization.
        if self.on_turn_complete is not None:
            result = self.on_turn_complete(event)

            if asyncio.iscoroutine(result):
                await result

        return []

    async def reset(self) -> None:

        self.reset_called = True


class FakeAssistant:
    """
    Fake assistant.

    Records completed turns and returns a deterministic
    response without executing LangGraph.
    """

    def __init__(
        self,
        response: str = "Hello from assistant.",
    ) -> None:

        self.response = response

        self.calls: list[
            tuple[str, str]
        ] = []

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
# WebM / Opus test audio
# ============================================================


def create_webm_audio(
    speech_duration_seconds: float = 1.0,
    silence_duration_seconds: float = (
        TRAILING_SILENCE_SECONDS
    ),
    sample_rate: int = 48000,
) -> bytes:
    """
    Generate a valid WebM/Opus audio stream containing:

        speech-energy tone
        +
        trailing silence

    The trailing silence is important because the real
    VAD needs silence after speech before it emits
    SPEECH_ENDED.

    The generated audio is synthetic and deterministic.
    It does not represent real human speech.
    """

    output = io.BytesIO()

    container = av.open(
        output,
        mode="w",
        format="webm",
    )

    stream = container.add_stream(
        "libopus",
        rate=sample_rate,
    )

    stream.layout = "mono"

    # --------------------------------------------------------
    # Audio configuration
    # --------------------------------------------------------

    speech_samples = int(
        sample_rate
        * speech_duration_seconds
    )

    silence_samples = int(
        sample_rate
        * silence_duration_seconds
    )

    total_samples = (
        speech_samples
        + silence_samples
    )

    samples_per_frame = 960

    frequency = 440.0
    amplitude = 0.25

    # --------------------------------------------------------
    # Generate speech-energy + silence
    # --------------------------------------------------------

    for start in range(
        0,
        total_samples,
        samples_per_frame,
    ):

        count = min(
            samples_per_frame,
            total_samples - start,
        )

        end = start + count

        # ----------------------------------------------------
        # Determine how much of this frame belongs to
        # the synthetic speech-energy region.
        # ----------------------------------------------------

        speech_count = 0

        if start < speech_samples:

            speech_end = min(
                end,
                speech_samples,
            )

            speech_count = (
                speech_end - start
            )

        # ----------------------------------------------------
        # Start with complete silence.
        # ----------------------------------------------------

        samples = np.zeros(
            count,
            dtype=np.int16,
        )

        # ----------------------------------------------------
        # Fill the speech region with a sine wave.
        # ----------------------------------------------------

        if speech_count > 0:

            time = (
                np.arange(speech_count)
                + start
            ) / sample_rate

            samples[:speech_count] = (
                amplitude
                * np.sin(
                    2
                    * np.pi
                    * frequency
                    * time
                )
                * 32767
            ).astype(np.int16)

        # ----------------------------------------------------
        # Convert NumPy array to PyAV AudioFrame.
        # ----------------------------------------------------

        frame = av.AudioFrame.from_ndarray(
            samples.reshape(1, -1),
            format="s16",
            layout="mono",
        )

        frame.sample_rate = sample_rate

        # ----------------------------------------------------
        # Encode frame as Opus.
        # ----------------------------------------------------

        for packet in stream.encode(frame):

            container.mux(packet)

    # --------------------------------------------------------
    # Flush encoder.
    # --------------------------------------------------------

    for packet in stream.encode():

        container.mux(packet)

    container.close()

    return output.getvalue()


# ============================================================
# Integration pipeline
# ============================================================


def create_integration_pipeline(
    *,
    transcriber=None,
    turn_detector=None,
    assistant=None,
) -> VoicePipeline:
    """
    Create a VoicePipeline using:

        REAL AudioDecoder
        REAL VoiceActivityDetector

    and:

        FAKE transcriber
        FAKE turn detector
        FAKE assistant
    """

    decoder = AudioDecoder(
        sample_rate=SAMPLE_RATE,
        frame_duration_ms=FRAME_DURATION_MS,
    )

    vad = create_vad(
        sample_rate=SAMPLE_RATE,
        frame_duration_ms=FRAME_DURATION_MS,
    )

    return VoicePipeline(
        session_id="integration-test-session",
        decoder=decoder,
        vad=vad,
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
    )


# ============================================================
# Helpers
# ============================================================


async def wait_until(
    predicate,
    *,
    timeout: float = 2.0,
    interval: float = 0.05,
) -> bool:
    """
    Wait until predicate() becomes True.

    Returns False if timeout is reached.
    """

    elapsed = 0.0

    while elapsed < timeout:

        if predicate():

            return True

        await asyncio.sleep(
            interval
        )

        elapsed += interval

    return False


# ============================================================
# Test 1
# ============================================================


@pytest.mark.integration
def test_real_decoder_and_vad_process_webm_audio():

    async def run():

        decoder = AudioDecoder(
            sample_rate=SAMPLE_RATE,
            frame_duration_ms=FRAME_DURATION_MS,
        )

        vad = create_vad(
            sample_rate=SAMPLE_RATE,
            frame_duration_ms=FRAME_DURATION_MS,
        )

        webm = create_webm_audio(
            speech_duration_seconds=1.0,
            silence_duration_seconds=(
                TRAILING_SILENCE_SECONDS
            ),
        )

        frames = await decoder.decode(
            webm
        )

        assert frames

        all_events = []

        for frame in frames:

            assert isinstance(
                frame,
                bytes,
            )

            assert len(frame) == (
                SAMPLES_PER_FRAME * 2
            )

            events = vad.process(
                frame
            )

            all_events.extend(
                events
            )

        # ----------------------------------------------------
        # The real VAD should detect both the beginning
        # and end of the speech segment.
        # ----------------------------------------------------

        event_types = [
            event.type
            for event in all_events
        ]

        assert (
            VADEventType.SPEECH_STARTED
            in event_types
        )

        assert (
            VADEventType.SPEECH_ENDED
            in event_types
        )

        # ----------------------------------------------------
        # SPEECH_ENDED should contain the accumulated
        # speech audio.
        # ----------------------------------------------------

        ended_events = [
            event
            for event in all_events
            if (
                event.type
                == VADEventType.SPEECH_ENDED
            )
        ]

        assert ended_events

        assert ended_events[-1].audio

        assert (
            ended_events[-1].speech_duration
            > 0
        )

        await decoder.close()

    asyncio.run(run())


# ============================================================
# Test 2
# ============================================================


@pytest.mark.integration
def test_pipeline_processes_real_webm_audio():

    async def run():

        pipeline = create_integration_pipeline()

        await pipeline.start()

        webm = create_webm_audio(
            speech_duration_seconds=1.0,
            silence_duration_seconds=(
                TRAILING_SILENCE_SECONDS
            ),
        )

        await pipeline.receive_audio(
            webm
        )

        assert pipeline.running is True

        await pipeline.close()

        assert pipeline.running is False

    asyncio.run(run())


# ============================================================
# Test 3
# ============================================================


@pytest.mark.integration
def test_real_audio_reaches_transcriber():

    async def run():

        transcriber = FakeTranscriber(
            text="hello world"
        )

        turn_detector = FakeTurnDetector()

        assistant = FakeAssistant()

        pipeline = create_integration_pipeline(
            transcriber=transcriber,
            turn_detector=turn_detector,
            assistant=assistant,
        )

        await pipeline.start()

        # ----------------------------------------------------
        # Speech followed by silence is required so the
        # real VAD can emit SPEECH_ENDED.
        # ----------------------------------------------------

        webm = create_webm_audio(
            speech_duration_seconds=1.0,
            silence_duration_seconds=(
                TRAILING_SILENCE_SECONDS
            ),
        )

        await pipeline.receive_audio(
            webm
        )

        # ----------------------------------------------------
        # WebM
        #   ↓
        # AudioDecoder
        #   ↓
        # VAD
        #   ↓
        # SPEECH_ENDED
        #   ↓
        # FakeTranscriber
        # ----------------------------------------------------

        reached = await wait_until(
            lambda: bool(
                transcriber.calls
            ),
            timeout=2.0,
        )

        assert reached

        pcm_audio, sample_rate = (
            transcriber.calls[0]
        )

        assert isinstance(
            pcm_audio,
            bytes,
        )

        assert len(
            pcm_audio
        ) > 0

        assert sample_rate == SAMPLE_RATE

        await pipeline.close()

    asyncio.run(run())


# ============================================================
# Test 4
# ============================================================


@pytest.mark.integration
def test_real_audio_reaches_turn_detector():

    async def run():

        transcriber = FakeTranscriber(
            text="hello world"
        )

        turn_detector = FakeTurnDetector()

        assistant = FakeAssistant()

        pipeline = create_integration_pipeline(
            transcriber=transcriber,
            turn_detector=turn_detector,
            assistant=assistant,
        )

        await pipeline.start()

        webm = create_webm_audio(
            speech_duration_seconds=1.0,
            silence_duration_seconds=(
                TRAILING_SILENCE_SECONDS
            ),
        )

        await pipeline.receive_audio(
            webm
        )

        # ----------------------------------------------------
        # WebM
        #   ↓
        # AudioDecoder
        #   ↓
        # PCM16
        #   ↓
        # VAD
        #   ↓
        # SPEECH_ENDED
        #   ↓
        # FakeTranscriber
        #   ↓
        # FakeTurnDetector
        # ----------------------------------------------------

        reached = await wait_until(
            lambda: bool(
                turn_detector.process_calls
            ),
            timeout=2.0,
        )

        assert reached

        assert (
            turn_detector.process_calls
            == ["hello world"]
        )

        await pipeline.close()

    asyncio.run(run())


# ============================================================
# Test 5
# ============================================================


@pytest.mark.integration
def test_completed_turn_reaches_assistant():

    async def run():

        transcriber = FakeTranscriber(
            text="hello world"
        )

        turn_detector = (
            CompletingFakeTurnDetector()
        )

        assistant = FakeAssistant(
            response="Hello from assistant."
        )

        assistant_started = []
        assistant_text = []
        assistant_completed = []

        # ----------------------------------------------------
        # Assistant lifecycle callbacks
        # ----------------------------------------------------

        async def on_assistant_started(
            turn_id: int,
        ) -> None:

            assistant_started.append(
                turn_id
            )

        async def on_assistant_text(
            text: str,
            turn_id: int,
        ) -> None:

            assistant_text.append(
                (
                    text,
                    turn_id,
                )
            )

        async def on_assistant_completed(
            turn_id: int,
        ) -> None:

            assistant_completed.append(
                turn_id
            )

        # ----------------------------------------------------
        # Construct pipeline.
        # ----------------------------------------------------

        pipeline = VoicePipeline(
            session_id="integration-test-session",
            decoder=AudioDecoder(
                sample_rate=SAMPLE_RATE,
                frame_duration_ms=FRAME_DURATION_MS,
            ),
            vad=create_vad(
                sample_rate=SAMPLE_RATE,
                frame_duration_ms=FRAME_DURATION_MS,
            ),
            transcriber=transcriber,
            turn_detector=turn_detector,
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

        # ----------------------------------------------------
        # IMPORTANT:
        #
        # Use the CURRENT create_webm_audio signature.
        #
        # speech_duration_seconds
        # silence_duration_seconds
        # ----------------------------------------------------

        webm = create_webm_audio(
            speech_duration_seconds=1.0,
            silence_duration_seconds=(
                TRAILING_SILENCE_SECONDS
            ),
        )

        await pipeline.receive_audio(
            webm
        )

        # ----------------------------------------------------
        # Wait for:
        #
        # WebM
        #   ↓
        # AudioDecoder
        #   ↓
        # VAD
        #   ↓
        # SPEECH_ENDED
        #   ↓
        # FakeTranscriber
        #   ↓
        # CompletingFakeTurnDetector
        #   ↓
        # TurnCompleted
        #   ↓
        # VoicePipeline
        #   ↓
        # FakeAssistant
        # ----------------------------------------------------

        reached = await wait_until(
            lambda: bool(
                assistant.calls
            ),
            timeout=2.0,
        )

        assert reached

        # ----------------------------------------------------
        # Verify assistant received the completed
        # user turn.
        # ----------------------------------------------------

        assert assistant.calls == [
            (
                "hello world",
                "integration-test-session",
            )
        ]

        # ----------------------------------------------------
        # Verify assistant lifecycle callbacks.
        # ----------------------------------------------------

        assert assistant_started == [
            1
        ]

        assert assistant_text == [
            (
                "Hello from assistant.",
                1,
            )
        ]

        assert assistant_completed == [
            1
        ]

        await pipeline.close()

    asyncio.run(run())