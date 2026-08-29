"""
Voice pipeline orchestration.

File:
    voice/pipeline.py

Responsibilities:
    - Receive encoded audio from the transport layer.
    - Decode audio into PCM16 frames.
    - Feed PCM16 frames into VAD.
    - Convert VAD lifecycle events into conversational events.
    - Run Whisper on completed speech segments.
    - Start the assistant graph after a completed user turn.
    - Consume streaming assistant TEXT / STATUS events.
    - Buffer assistant text into complete sentences.
    - Send complete sentences to TTS.
    - Forward generated audio to the transport layer.
    - Cancel stale assistant / TTS work during interruption.
    - Cleanly shut down all asynchronous work.

This module is the ORCHESTRATOR.

The logging in this module is intentionally detailed.

It is designed to answer:

    - When did audio arrive?
    - How large was it?
    - How long did decoding take?
    - How many PCM frames were produced?
    - When did VAD detect speech?
    - When did speech end?
    - How long did Whisper take?
    - When did the transcript arrive?
    - When was the user turn completed?
    - When did the graph start?
    - When did graph tokens arrive?
    - What is currently buffered?
    - When did a sentence become complete?
    - When did TTS start?
    - How long did TTS take?
    - When did audio chunks leave TTS?
    - When did audio reach the transport callback?
    - When was the assistant interrupted?
    - How much time passed between interruption and cancellation?
    - Which asynchronous execution produced an event?
    - Are stale events being discarded?
    - Are components being instantiated repeatedly?

Timing uses time.perf_counter() because it is intended for
measuring elapsed durations.

The normal logging timestamp is provided by Python logging's
formatter. The explicit elapsed_ms values below are relative
latency measurements.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Awaitable, Callable, Optional

from .audio_decoder import AudioDecoder
from .config import (
    INTERRUPTION_ENABLED,
    INTERRUPTION_MIN_SPEECH_SECONDS,
)
from .graph_runner import VoiceGraphRunner
from .models import (
    SpeechStarted,
    TranscriptChanged,
    TurnCompleted,
    VoiceGraphEvent,
    VoiceGraphEventType,
)
from .synthesis import (
    SpeechSynthesizer,
    speech_synthesizer,
)
from .transcription import (
    WhisperTranscriber,
    whisper_transcriber,
)
from .turn_detector import TurnDetector
from .vad import (
    VADEvent,
    VADEventType,
    VoiceActivityDetector,
    create_vad,
)

logger = logging.getLogger(__name__)


# ============================================================
# Callback types
# ============================================================

SpeechStartedCallback = Callable[
    [SpeechStarted],
    Awaitable[None],
]

TranscriptChangedCallback = Callable[
    [TranscriptChanged],
    Awaitable[None],
]

TurnCompletedCallback = Callable[
    [TurnCompleted],
    Awaitable[None],
]

AssistantStartedCallback = Callable[
    [int],
    Awaitable[None],
]

AssistantStatusCallback = Callable[
    [str, int],
    Awaitable[None],
]

AssistantTextCallback = Callable[
    [str, int],
    Awaitable[None],
]

AssistantAudioCallback = Callable[
    [bytes, int],
    Awaitable[None],
]

AssistantCompletedCallback = Callable[
    [int],
    Awaitable[None],
]

AssistantErrorCallback = Callable[
    [int, Exception],
    Awaitable[None],
]


# ============================================================
# Voice Pipeline
# ============================================================


class VoicePipeline:
    """
    Coordinates the complete voice interaction lifecycle.

    Important ownership:

        VAD
            owns speech detection.

        TurnDetector
            owns conversational turn state.

        Whisper
            owns transcription.

        VoiceGraphRunner
            owns assistant/graph execution.

        SpeechSynthesizer
            owns text-to-speech.

        Pipeline
            owns orchestration and cancellation.

    The pipeline does not create WebSocket events itself.
    The session / transport layer converts callbacks into
    WebSocket events.

    Logging:

        This class also records detailed timing information so
        that end-to-end latency can be diagnosed without having
        to guess which component is responsible.
    """

    def __init__(
        self,
        session_id: str,
        transcriber: Optional[WhisperTranscriber] = None,
        turn_detector: Optional[TurnDetector] = None,
        graph_runner: Optional[VoiceGraphRunner] = None,
        decoder: Optional[AudioDecoder] = None,
        vad: Optional[VoiceActivityDetector] = None,
        synthesizer: Optional[SpeechSynthesizer] = None,
        on_speech_started: Optional[SpeechStartedCallback] = None,
        on_transcript_changed: Optional[TranscriptChangedCallback] = None,
        on_turn_complete: Optional[TurnCompletedCallback] = None,
        on_assistant_started: Optional[AssistantStartedCallback] = None,
        on_assistant_status: Optional[AssistantStatusCallback] = None,
        on_assistant_text: Optional[AssistantTextCallback] = None,
        on_assistant_audio: Optional[AssistantAudioCallback] = None,
        on_assistant_completed: Optional[AssistantCompletedCallback] = None,
        on_assistant_error: Optional[AssistantErrorCallback] = None,
    ) -> None:

        if not session_id:
            raise ValueError("session_id must not be empty.")

        # ----------------------------------------------------
        # Pipeline lifetime clock.
        #
        # All elapsed_ms measurements are relative to this
        # pipeline instance.
        # ----------------------------------------------------

        self._created_at = time.perf_counter()

        self.session_id = session_id

        # ----------------------------------------------------
        # Component construction.
        #
        # IMPORTANT:
        #
        # We explicitly log whether a dependency was injected
        # or constructed here.
        #
        # This helps identify accidental repeated construction
        # of expensive singleton-like resources such as:
        #
        #     Whisper
        #     TTS
        #     model loaders
        #     graph infrastructure
        # ----------------------------------------------------

        decoder_injected = decoder is not None
        vad_injected = vad is not None
        transcriber_injected = transcriber is not None
        turn_detector_injected = turn_detector is not None
        graph_runner_injected = graph_runner is not None
        synthesizer_injected = synthesizer is not None

        self.decoder = decoder or AudioDecoder(
            sample_rate=16000,
            frame_duration_ms=20,
        )

        self.vad = vad or create_vad(
            sample_rate=16000,
            frame_duration_ms=20,
        )

        self.transcriber = transcriber or whisper_transcriber()

        self.turn_detector = turn_detector or TurnDetector()

        self.graph_runner = graph_runner or VoiceGraphRunner()

        self.synthesizer = synthesizer or speech_synthesizer()

        logger.info(
            "[PIPELINE_INIT] "
            "session=%s "
            "elapsed_ms=%.2f "
            "decoder=%s(injected=%s) "
            "vad=%s(injected=%s) "
            "transcriber=%s(injected=%s) "
            "turn_detector=%s(injected=%s) "
            "graph_runner=%s(injected=%s) "
            "synthesizer=%s(injected=%s)",
            self.session_id,
            self._elapsed_ms(),
            type(self.decoder).__name__,
            decoder_injected,
            type(self.vad).__name__,
            vad_injected,
            type(self.transcriber).__name__,
            transcriber_injected,
            type(self.turn_detector).__name__,
            turn_detector_injected,
            type(self.graph_runner).__name__,
            graph_runner_injected,
            type(self.synthesizer).__name__,
            synthesizer_injected,
        )

        # ----------------------------------------------------
        # Transport callbacks.
        # ----------------------------------------------------

        self.on_speech_started = on_speech_started

        self.on_transcript_changed = on_transcript_changed

        self.on_turn_complete = on_turn_complete

        self.on_assistant_started = on_assistant_started

        self.on_assistant_status = on_assistant_status

        self.on_assistant_text = on_assistant_text

        self.on_assistant_audio = on_assistant_audio

        self.on_assistant_completed = on_assistant_completed

        self.on_assistant_error = on_assistant_error

        # ====================================================
        # Runtime state
        # ====================================================

        self.running = False

        self._closing = False

        # ----------------------------------------------------
        # Assistant execution.
        # ----------------------------------------------------

        self.assistant_task: Optional[asyncio.Task] = None

        self.assistant_turn_id: Optional[int] = None

        # ----------------------------------------------------
        # Pending Whisper tasks.
        # ----------------------------------------------------

        self._speech_transcription_tasks: set[asyncio.Task] = set()

        # ----------------------------------------------------
        # Pipeline generation.
        # ----------------------------------------------------

        self._generation = 0

        # ----------------------------------------------------
        # Audio counters.
        #
        # Useful for diagnosing transport / decoder behavior.
        # ----------------------------------------------------

        self._received_audio_chunks = 0
        self._received_audio_bytes = 0

        self._decoded_frames = 0
        self._decoded_pcm_bytes = 0

        # ----------------------------------------------------
        # Assistant counters.
        # ----------------------------------------------------

        self._assistant_graph_events = 0
        self._assistant_text_tokens = 0
        self._assistant_audio_chunks = 0
        self._assistant_audio_bytes = 0

        logger.info(
            "[PIPELINE_READY] session=%s elapsed_ms=%.2f generation=%d",
            self.session_id,
            self._elapsed_ms(),
            self._generation,
        )

    # ========================================================
    # Timing helpers
    # ========================================================

    def _elapsed_ms(self) -> float:
        """
        Return milliseconds elapsed since pipeline construction.
        """

        return (time.perf_counter() - self._created_at) * 1000.0

    @staticmethod
    def _now() -> float:
        """
        Return a high-resolution monotonic timestamp.

        Used for measuring individual operations.
        """

        return time.perf_counter()

    @staticmethod
    def _duration_ms(
        started_at: float,
    ) -> float:
        """
        Calculate elapsed milliseconds from a perf_counter
        timestamp.
        """

        return (time.perf_counter() - started_at) * 1000.0

    # ========================================================
    # Start
    # ========================================================

    async def start(self) -> None:
        """
        Start reusable pipeline components.

        Starting an already-running pipeline is idempotent.
        """

        if self.running:
            logger.debug(
                "[PIPELINE_START_SKIP] "
                "session=%s "
                "elapsed_ms=%.2f "
                "reason=already_running",
                self.session_id,
                self._elapsed_ms(),
            )

            return

        start_time = self._now()

        self._closing = False

        logger.info(
            "[PIPELINE_START] session=%s elapsed_ms=%.2f generation=%d",
            self.session_id,
            self._elapsed_ms(),
            self._generation,
        )

        # ----------------------------------------------------
        # Start Whisper.
        # ----------------------------------------------------

        component_start = self._now()

        logger.info(
            "[TRANSCRIBER_START] session=%s elapsed_ms=%.2f component=%s",
            self.session_id,
            self._elapsed_ms(),
            type(self.transcriber).__name__,
        )

        await self.transcriber.start()

        logger.info(
            "[TRANSCRIBER_READY] session=%s elapsed_ms=%.2f duration_ms=%.2f",
            self.session_id,
            self._elapsed_ms(),
            self._duration_ms(component_start),
        )

        # ----------------------------------------------------
        # Start TTS.
        # ----------------------------------------------------

        component_start = self._now()

        logger.info(
            "[SYNTHESIZER_START] session=%s elapsed_ms=%.2f component=%s",
            self.session_id,
            self._elapsed_ms(),
            type(self.synthesizer).__name__,
        )

        await self.synthesizer.start()

        logger.info(
            "[SYNTHESIZER_READY] session=%s elapsed_ms=%.2f duration_ms=%.2f",
            self.session_id,
            self._elapsed_ms(),
            self._duration_ms(component_start),
        )

        self.running = True

        logger.info(
            "[PIPELINE_STARTED] session=%s elapsed_ms=%.2f startup_duration_ms=%.2f",
            self.session_id,
            self._elapsed_ms(),
            self._duration_ms(start_time),
        )

    # ========================================================
    # Receive audio
    # ========================================================

    async def receive_audio(
        self,
        audio_chunk: bytes,
    ) -> None:
        """
        Feed one encoded audio chunk into the pipeline.
        """

        if not self.running:
            logger.debug(
                "[AUDIO_DROP] session=%s elapsed_ms=%.2f reason=pipeline_not_running",
                self.session_id,
                self._elapsed_ms(),
            )

            return

        if not audio_chunk:
            logger.debug(
                "[AUDIO_DROP] session=%s elapsed_ms=%.2f reason=empty_chunk",
                self.session_id,
                self._elapsed_ms(),
            )

            return

        receive_time = self._now()

        self._received_audio_chunks += 1
        self._received_audio_bytes += len(audio_chunk)

        chunk_id = self._received_audio_chunks

        logger.debug(
            "[AUDIO_RECEIVED] "
            "session=%s "
            "chunk=%d "
            "bytes=%d "
            "total_bytes=%d "
            "elapsed_ms=%.2f",
            self.session_id,
            chunk_id,
            len(audio_chunk),
            self._received_audio_bytes,
            self._elapsed_ms(),
        )

        # ----------------------------------------------------
        # Decode encoded transport audio into PCM16 frames.
        # ----------------------------------------------------

        decode_start = self._now()

        frames = await self.decoder.decode(audio_chunk)

        decode_duration = self._duration_ms(decode_start)

        if not self.running:
            logger.debug(
                "[AUDIO_DECODE_ABORT] "
                "session=%s "
                "chunk=%d "
                "elapsed_ms=%.2f "
                "decode_ms=%.2f "
                "reason=pipeline_stopped",
                self.session_id,
                chunk_id,
                self._elapsed_ms(),
                decode_duration,
            )

            return

        logger.debug(
            "[AUDIO_DECODED] "
            "session=%s "
            "chunk=%d "
            "frames=%d "
            "decode_ms=%.2f "
            "receive_to_decode_ms=%.2f",
            self.session_id,
            chunk_id,
            len(frames),
            decode_duration,
            self._duration_ms(receive_time),
        )

        # ----------------------------------------------------
        # Process every decoded frame through VAD.
        # ----------------------------------------------------

        for frame_index, frame in enumerate(frames):
            if not self.running:
                return

            if not frame:
                continue

            self._decoded_frames += 1
            self._decoded_pcm_bytes += len(frame)

            logger.debug(
                "[PCM_FRAME] "
                "session=%s "
                "chunk=%d "
                "frame=%d "
                "bytes=%d "
                "total_frames=%d "
                "elapsed_ms=%.2f",
                self.session_id,
                chunk_id,
                frame_index,
                len(frame),
                self._decoded_frames,
                self._elapsed_ms(),
            )

            vad_start = self._now()

            vad_events = self.vad.process(frame)

            vad_duration = self._duration_ms(vad_start)

            if vad_events:
                logger.debug(
                    "[VAD_EVENTS] "
                    "session=%s "
                    "chunk=%d "
                    "frame=%d "
                    "count=%d "
                    "vad_ms=%.2f "
                    "elapsed_ms=%.2f",
                    self.session_id,
                    chunk_id,
                    frame_index,
                    len(vad_events),
                    vad_duration,
                    self._elapsed_ms(),
                )

            for vad_event in vad_events:
                if not self.running:
                    return

                await self._handle_vad_event(vad_event)

    # ========================================================
    # VAD
    # ========================================================

    async def _handle_vad_event(
        self,
        event: VADEvent,
    ) -> None:
        """
        Convert a VAD event into conversational processing.
        """

        if not self.running:
            return

        logger.info(
            "[VAD_EVENT] "
            "session=%s "
            "type=%s "
            "duration=%.3f "
            "audio_bytes=%d "
            "elapsed_ms=%.2f",
            self.session_id,
            event.type.name,
            event.speech_duration,
            len(event.audio or b""),
            self._elapsed_ms(),
        )

        if event.type == VADEventType.SPEECH_STARTED:
            await self._handle_speech_started(event)

            return

        if event.type == VADEventType.SPEECH_ENDED:
            await self._handle_speech_ended(event)

    # ========================================================
    # Speech started
    # ========================================================

    async def _handle_speech_started(
        self,
        event: VADEvent,
    ) -> None:
        """
        Handle confirmed user speech.
        """

        if not self.running:
            return

        logger.info(
            "[SPEECH_STARTED] "
            "session=%s "
            "speech_duration=%.3fs "
            "assistant_turn=%s "
            "elapsed_ms=%.2f",
            self.session_id,
            event.speech_duration,
            self.assistant_turn_id,
            self._elapsed_ms(),
        )

        # ----------------------------------------------------
        # Barge-in.
        # ----------------------------------------------------

        if (
            INTERRUPTION_ENABLED
            and self.assistant_turn_id is not None
            and event.speech_duration >= INTERRUPTION_MIN_SPEECH_SECONDS
        ):
            logger.info(
                "[BARGE_IN_DETECTED] "
                "session=%s "
                "turn=%s "
                "speech_duration=%.3fs "
                "threshold=%.3fs "
                "elapsed_ms=%.2f",
                self.session_id,
                self.assistant_turn_id,
                event.speech_duration,
                INTERRUPTION_MIN_SPEECH_SECONDS,
                self._elapsed_ms(),
            )

            await self.interrupt_assistant()

        # ----------------------------------------------------
        # Turn detector.
        # ----------------------------------------------------

        detector_start = self._now()

        turn_events = await self.turn_detector.process_vad_event(event)

        logger.debug(
            "[TURN_DETECTOR_VAD] "
            "session=%s "
            "type=%s "
            "events=%d "
            "duration_ms=%.2f "
            "elapsed_ms=%.2f",
            self.session_id,
            event.type.name,
            len(turn_events),
            self._duration_ms(detector_start),
            self._elapsed_ms(),
        )

        for turn_event in turn_events:
            if not self.running:
                return

            if isinstance(
                turn_event,
                SpeechStarted,
            ):
                logger.info(
                    "[TURN_SPEECH_STARTED] session=%s turn=%s elapsed_ms=%.2f",
                    self.session_id,
                    turn_event.turn_id,
                    self._elapsed_ms(),
                )

                if self.on_speech_started:
                    callback_start = self._now()

                    await self.on_speech_started(turn_event)

                    logger.debug(
                        "[CALLBACK_DONE] "
                        "session=%s "
                        "callback=on_speech_started "
                        "duration_ms=%.2f "
                        "elapsed_ms=%.2f",
                        self.session_id,
                        self._duration_ms(callback_start),
                        self._elapsed_ms(),
                    )

    # ========================================================
    # Speech ended
    # ========================================================

    async def _handle_speech_ended(
        self,
        event: VADEvent,
    ) -> None:
        """
        Start asynchronous transcription for a completed
        VAD speech segment.
        """

        if not self.running:
            return

        if not event.audio:
            logger.warning(
                "[SPEECH_ENDED_NO_AUDIO] session=%s elapsed_ms=%.2f",
                self.session_id,
                self._elapsed_ms(),
            )

            return

        if event.speech_duration <= 0:
            logger.warning(
                "[SPEECH_ENDED_INVALID] session=%s duration=%.3f elapsed_ms=%.2f",
                self.session_id,
                event.speech_duration,
                self._elapsed_ms(),
            )

            return

        generation = self._generation

        logger.info(
            "[SPEECH_ENDED] "
            "session=%s "
            "speech_duration=%.3fs "
            "audio_bytes=%d "
            "generation=%d "
            "elapsed_ms=%.2f",
            self.session_id,
            event.speech_duration,
            len(event.audio),
            generation,
            self._elapsed_ms(),
        )

        # ----------------------------------------------------
        # Whisper runs independently.
        # ----------------------------------------------------

        task = asyncio.create_task(
            self._transcribe_speech(
                pcm_audio=event.audio,
                speech_end_event=event,
                generation=generation,
            )
        )

        self._speech_transcription_tasks.add(task)

        logger.debug(
            "[WHISPER_TASK_CREATED] "
            "session=%s "
            "generation=%d "
            "pending_tasks=%d "
            "elapsed_ms=%.2f",
            self.session_id,
            generation,
            len(self._speech_transcription_tasks),
            self._elapsed_ms(),
        )

        task.add_done_callback(self._speech_transcription_tasks.discard)

    # ========================================================
    # Transcription
    # ========================================================

    async def _transcribe_speech(
        self,
        pcm_audio: bytes,
        speech_end_event: VADEvent,
        generation: int,
    ) -> None:
        """
        Transcribe one completed speech segment.
        """

        whisper_start = self._now()

        logger.info(
            "[WHISPER_START] "
            "session=%s "
            "audio_bytes=%d "
            "speech_duration=%.3fs "
            "generation=%d "
            "elapsed_ms=%.2f",
            self.session_id,
            len(pcm_audio),
            speech_end_event.speech_duration,
            generation,
            self._elapsed_ms(),
        )

        try:
            result = await self.transcriber.transcribe_pcm(
                pcm_audio,
                sample_rate=16000,
            )

            whisper_duration = self._duration_ms(whisper_start)

            logger.info(
                "[WHISPER_COMPLETE] "
                "session=%s "
                "duration_ms=%.2f "
                "has_speech=%s "
                "text_chars=%d "
                "elapsed_ms=%.2f",
                self.session_id,
                whisper_duration,
                result.has_speech,
                len(result.text or ""),
                self._elapsed_ms(),
            )

            if not self.running:
                logger.debug(
                    "[WHISPER_STALE] "
                    "session=%s "
                    "reason=pipeline_stopped "
                    "elapsed_ms=%.2f",
                    self.session_id,
                    self._elapsed_ms(),
                )

                return

            if generation != self._generation:
                logger.debug(
                    "[WHISPER_STALE] "
                    "session=%s "
                    "task_generation=%d "
                    "current_generation=%d "
                    "elapsed_ms=%.2f",
                    self.session_id,
                    generation,
                    self._generation,
                    self._elapsed_ms(),
                )

                return

            if not result.has_speech:
                logger.info(
                    "[WHISPER_NO_SPEECH] session=%s elapsed_ms=%.2f",
                    self.session_id,
                    self._elapsed_ms(),
                )

                return

            transcript = result.text.strip()

            if not transcript:
                logger.info(
                    "[WHISPER_EMPTY_TRANSCRIPT] session=%s elapsed_ms=%.2f",
                    self.session_id,
                    self._elapsed_ms(),
                )

                return

            logger.info(
                "[TRANSCRIPT_READY] session=%s text=%r chars=%d elapsed_ms=%.2f",
                self.session_id,
                transcript,
                len(transcript),
                self._elapsed_ms(),
            )

            # ------------------------------------------------
            # Associate transcript with current turn.
            # ------------------------------------------------

            detector_start = self._now()

            transcript_events = await self.turn_detector.process_transcript(transcript)

            logger.debug(
                "[TURN_DETECTOR_TRANSCRIPT] "
                "session=%s "
                "events=%d "
                "duration_ms=%.2f "
                "elapsed_ms=%.2f",
                self.session_id,
                len(transcript_events),
                self._duration_ms(detector_start),
                self._elapsed_ms(),
            )

            for turn_event in transcript_events:
                if not self.running:
                    return

                if isinstance(
                    turn_event,
                    SpeechStarted,
                ):
                    logger.info(
                        "[TURN_EVENT] "
                        "session=%s "
                        "type=SpeechStarted "
                        "turn=%s "
                        "elapsed_ms=%.2f",
                        self.session_id,
                        turn_event.turn_id,
                        self._elapsed_ms(),
                    )

                    if self.on_speech_started:
                        await self.on_speech_started(turn_event)

                elif isinstance(
                    turn_event,
                    TranscriptChanged,
                ):
                    logger.info(
                        "[TURN_EVENT] "
                        "session=%s "
                        "type=TranscriptChanged "
                        "turn=%s "
                        "text=%r "
                        "elapsed_ms=%.2f",
                        self.session_id,
                        turn_event.turn_id,
                        turn_event.text,
                        self._elapsed_ms(),
                    )

                    if self.on_transcript_changed:
                        await self.on_transcript_changed(turn_event)

                elif isinstance(
                    turn_event,
                    TurnCompleted,
                ):
                    logger.info(
                        "[TURN_EVENT] "
                        "session=%s "
                        "type=TurnCompleted "
                        "turn=%s "
                        "text=%r "
                        "elapsed_ms=%.2f",
                        self.session_id,
                        turn_event.turn_id,
                        turn_event.text,
                        self._elapsed_ms(),
                    )

                    await self._handle_turn_complete(turn_event)

            # ------------------------------------------------
            # Current TurnDetector contract:
            #
            # transcript first
            # then VAD SPEECH_ENDED
            # ------------------------------------------------

            if not self.running:
                return

            if generation != self._generation:
                return

            detector_start = self._now()

            turn_events = await self.turn_detector.process_vad_event(speech_end_event)

            logger.debug(
                "[TURN_DETECTOR_SPEECH_END] "
                "session=%s "
                "events=%d "
                "duration_ms=%.2f "
                "elapsed_ms=%.2f",
                self.session_id,
                len(turn_events),
                self._duration_ms(detector_start),
                self._elapsed_ms(),
            )

            for turn_event in turn_events:
                if not self.running:
                    return

                if generation != self._generation:
                    return

                if isinstance(
                    turn_event,
                    TurnCompleted,
                ):
                    logger.info(
                        "[TURN_COMPLETED_AFTER_VAD_END] "
                        "session=%s "
                        "turn=%s "
                        "text=%r "
                        "elapsed_ms=%.2f",
                        self.session_id,
                        turn_event.turn_id,
                        turn_event.text,
                        self._elapsed_ms(),
                    )

                    await self._handle_turn_complete(turn_event)

        except asyncio.CancelledError:
            logger.info(
                "[WHISPER_CANCELLED] session=%s elapsed_ms=%.2f running=%s",
                self.session_id,
                self._elapsed_ms(),
                self.running,
            )

            raise

        except Exception:
            logger.exception(
                "[WHISPER_ERROR] session=%s elapsed_ms=%.2f",
                self.session_id,
                self._elapsed_ms(),
            )

    # ========================================================
    # Turn completed
    # ========================================================

    async def _handle_turn_complete(
        self,
        completed: TurnCompleted,
    ) -> None:
        """
        Start assistant processing for a completed user turn.
        """

        if not self.running:
            return

        text = completed.text.strip()

        if not text:
            return

        logger.info(
            "[USER_TURN_COMPLETE] session=%s turn=%s text=%r chars=%d elapsed_ms=%.2f",
            self.session_id,
            completed.turn_id,
            text,
            len(text),
            self._elapsed_ms(),
        )

        # ----------------------------------------------------
        # Transport notification.
        # ----------------------------------------------------

        if self.on_turn_complete:
            callback_start = self._now()

            await self.on_turn_complete(completed)

            logger.debug(
                "[CALLBACK_DONE] "
                "session=%s "
                "callback=on_turn_complete "
                "duration_ms=%.2f "
                "elapsed_ms=%.2f",
                self.session_id,
                self._duration_ms(callback_start),
                self._elapsed_ms(),
            )

        # ----------------------------------------------------
        # Start assistant.
        # ----------------------------------------------------

        await self._start_assistant(
            user_text=text,
            turn_id=completed.turn_id,
        )

    # ========================================================
    # Sentence extraction
    # ========================================================

    @staticmethod
    def _extract_complete_sentences(
        buffer: str,
    ) -> tuple[list[str], str]:
        """
        Extract complete sentences from a streaming text buffer.
        """

        sentences: list[str] = []

        start = 0

        for index, char in enumerate(buffer):
            if char not in ".!?":
                continue

            is_end_of_text = index == len(buffer) - 1

            next_is_space = not is_end_of_text and buffer[index + 1].isspace()

            if not is_end_of_text and not next_is_space:
                continue

            sentence = buffer[start : index + 1].strip()

            if sentence:
                sentences.append(sentence)

            start = index + 1

        remainder = buffer[start:].strip()

        return sentences, remainder

    # ========================================================
    # Start assistant
    # ========================================================

    async def _start_assistant(
        self,
        user_text: str,
        turn_id: int,
    ) -> None:
        """
        Start consuming the assistant graph stream.
        """

        logger.info(
            "[ASSISTANT_START_REQUEST] "
            "session=%s "
            "turn=%s "
            "text=%r "
            "previous_turn=%s "
            "generation=%d "
            "elapsed_ms=%.2f",
            self.session_id,
            turn_id,
            user_text,
            self.assistant_turn_id,
            self._generation,
            self._elapsed_ms(),
        )

        # ----------------------------------------------------
        # Only one assistant execution may own the output
        # channel.
        # ----------------------------------------------------

        await self.cancel_assistant()

        if not self.running:
            return

        self.assistant_turn_id = turn_id

        logger.info(
            "[ASSISTANT_OWNERSHIP_ACQUIRED] "
            "session=%s "
            "turn=%s "
            "generation=%d "
            "elapsed_ms=%.2f",
            self.session_id,
            turn_id,
            self._generation,
            self._elapsed_ms(),
        )

        if self.on_assistant_started:
            callback_start = self._now()

            await self.on_assistant_started(turn_id)

            logger.debug(
                "[CALLBACK_DONE] "
                "session=%s "
                "callback=on_assistant_started "
                "turn=%s "
                "duration_ms=%.2f "
                "elapsed_ms=%.2f",
                self.session_id,
                turn_id,
                self._duration_ms(callback_start),
                self._elapsed_ms(),
            )

        generation = self._generation

        task = asyncio.create_task(
            self._consume_assistant_stream(
                user_text=user_text,
                turn_id=turn_id,
                generation=generation,
            )
        )

        self.assistant_task = task

        logger.info(
            "[ASSISTANT_TASK_CREATED] session=%s turn=%s generation=%d elapsed_ms=%.2f",
            self.session_id,
            turn_id,
            generation,
            self._elapsed_ms(),
        )

        try:
            await task

        except asyncio.CancelledError:
            logger.info(
                "[ASSISTANT_TASK_CANCELLED] session=%s turn=%s elapsed_ms=%.2f",
                self.session_id,
                turn_id,
                self._elapsed_ms(),
            )

        except Exception as exc:
            logger.exception(
                "[ASSISTANT_TASK_ERROR] session=%s turn=%s elapsed_ms=%.2f",
                self.session_id,
                turn_id,
                self._elapsed_ms(),
            )

            if self.running and self.on_assistant_error:
                await self.on_assistant_error(
                    turn_id,
                    exc,
                )

        finally:
            if self.assistant_task is task:
                self.assistant_task = None

                logger.debug(
                    "[ASSISTANT_TASK_CLEARED] session=%s turn=%s elapsed_ms=%.2f",
                    self.session_id,
                    turn_id,
                    self._elapsed_ms(),
                )

    # ========================================================
    # Consume graph stream
    # ========================================================

    async def _consume_assistant_stream(
        self,
        user_text: str,
        turn_id: int,
        generation: int,
    ) -> None:
        """
        Consume streaming graph events.

        TEXT is accumulated into a sentence buffer.

        The frontend still receives streamed text immediately.

        TTS receives complete buffered sentences.

        This gives us:

            graph
              ↓
            text stream
              ↓
            frontend text immediately

            meanwhile

            sentence buffer
              ↓
            complete sentence
              ↓
            TTS
              ↓
            audio stream
        """

        assistant_start = self._now()

        sentence_buffer = ""

        total_text = ""

        logger.info(
            "[GRAPH_STREAM_START] "
            "session=%s "
            "turn=%s "
            "generation=%d "
            "user_chars=%d "
            "elapsed_ms=%.2f",
            self.session_id,
            turn_id,
            generation,
            len(user_text),
            self._elapsed_ms(),
        )

        try:
            async for graph_event in self.graph_runner.stream(
                user_text,
                self.session_id,
            ):
                event_received_at = self._now()

                if not self._assistant_is_current(
                    turn_id,
                    generation,
                ):
                    logger.debug(
                        "[GRAPH_EVENT_STALE] "
                        "session=%s "
                        "turn=%s "
                        "generation=%d "
                        "current_generation=%d "
                        "elapsed_ms=%.2f",
                        self.session_id,
                        turn_id,
                        generation,
                        self._generation,
                        self._elapsed_ms(),
                    )

                    return

                self._assistant_graph_events += 1

                event_id = self._assistant_graph_events

                if not isinstance(
                    graph_event,
                    VoiceGraphEvent,
                ):
                    logger.warning(
                        "[GRAPH_EVENT_INVALID] "
                        "session=%s "
                        "turn=%s "
                        "event=%d "
                        "type=%s "
                        "elapsed_ms=%.2f",
                        self.session_id,
                        turn_id,
                        event_id,
                        type(graph_event).__name__,
                        self._elapsed_ms(),
                    )

                    continue

                logger.debug(
                    "[GRAPH_EVENT] "
                    "session=%s "
                    "turn=%s "
                    "event=%d "
                    "type=%s "
                    "content_chars=%d "
                    "elapsed_ms=%.2f "
                    "graph_since_start_ms=%.2f",
                    self.session_id,
                    turn_id,
                    event_id,
                    graph_event.type.name,
                    len(graph_event.content or ""),
                    self._elapsed_ms(),
                    self._duration_ms(assistant_start),
                )

                # ==========================================
                # STATUS
                # ==========================================

                if graph_event.type == VoiceGraphEventType.STATUS:
                    status = graph_event.content.strip()

                    if not status:
                        continue

                    logger.info(
                        "[ASSISTANT_STATUS] "
                        "session=%s "
                        "turn=%s "
                        "status=%r "
                        "elapsed_ms=%.2f",
                        self.session_id,
                        turn_id,
                        status,
                        self._elapsed_ms(),
                    )

                    if self.on_assistant_status:
                        callback_start = self._now()

                        await self.on_assistant_status(
                            status,
                            turn_id,
                        )

                        logger.debug(
                            "[CALLBACK_DONE] "
                            "session=%s "
                            "callback=on_assistant_status "
                            "turn=%s "
                            "duration_ms=%.2f "
                            "elapsed_ms=%.2f",
                            self.session_id,
                            turn_id,
                            self._duration_ms(callback_start),
                            self._elapsed_ms(),
                        )

                    continue

                # ==========================================
                # TEXT
                # ==========================================

                if graph_event.type != VoiceGraphEventType.TEXT:
                    continue

                token = graph_event.content

                if not token:
                    continue

                self._assistant_text_tokens += 1

                total_text += token

                # ------------------------------------------------
                # IMPORTANT:
                #
                # This is the actual text buffer.
                #
                # The buffer persists across graph events until
                # punctuation creates a complete sentence.
                # ------------------------------------------------

                sentence_buffer += token

                logger.debug(
                    "[TEXT_BUFFER_APPEND] "
                    "session=%s "
                    "turn=%s "
                    "token=%r "
                    "token_chars=%d "
                    "buffer_chars=%d "
                    "buffer=%r "
                    "elapsed_ms=%.2f",
                    self.session_id,
                    turn_id,
                    token,
                    len(token),
                    len(sentence_buffer),
                    sentence_buffer,
                    self._elapsed_ms(),
                )

                # ------------------------------------------------
                # Send streamed answer text to frontend.
                #
                # This is intentionally immediate.
                # ------------------------------------------------

                if self.on_assistant_text:
                    callback_start = self._now()

                    await self.on_assistant_text(
                        token,
                        turn_id,
                    )

                    logger.debug(
                        "[FRONTEND_TEXT_OUT] "
                        "session=%s "
                        "turn=%s "
                        "text=%r "
                        "callback_ms=%.2f "
                        "elapsed_ms=%.2f",
                        self.session_id,
                        turn_id,
                        token,
                        self._duration_ms(callback_start),
                        self._elapsed_ms(),
                    )

                # ------------------------------------------------
                # Extract complete sentences.
                # ------------------------------------------------

                before_buffer = sentence_buffer

                (
                    sentences,
                    sentence_buffer,
                ) = self._extract_complete_sentences(sentence_buffer)

                if sentences:
                    logger.info(
                        "[TEXT_SENTENCE_READY] "
                        "session=%s "
                        "turn=%s "
                        "sentences=%d "
                        "before_chars=%d "
                        "remaining_chars=%d "
                        "remaining=%r "
                        "elapsed_ms=%.2f",
                        self.session_id,
                        turn_id,
                        len(sentences),
                        len(before_buffer),
                        len(sentence_buffer),
                        sentence_buffer,
                        self._elapsed_ms(),
                    )

                # ------------------------------------------------
                # Synthesize each completed sentence.
                # ------------------------------------------------

                for sentence_index, sentence in enumerate(
                    sentences,
                    start=1,
                ):
                    logger.info(
                        "[TTS_QUEUE_SENTENCE] "
                        "session=%s "
                        "turn=%s "
                        "sentence_index=%d "
                        "text=%r "
                        "remaining_buffer=%r "
                        "elapsed_ms=%.2f",
                        self.session_id,
                        turn_id,
                        sentence_index,
                        sentence,
                        sentence_buffer,
                        self._elapsed_ms(),
                    )

                    success = await self._synthesize_sentence(
                        sentence=sentence,
                        turn_id=turn_id,
                        generation=generation,
                    )

                    if not success:
                        logger.info(
                            "[TTS_SENTENCE_ABORTED] "
                            "session=%s "
                            "turn=%s "
                            "sentence=%r "
                            "elapsed_ms=%.2f",
                            self.session_id,
                            turn_id,
                            sentence,
                            self._elapsed_ms(),
                        )

                        return

                # ------------------------------------------------
                # Useful latency diagnostic:
                #
                # How long did processing of this graph event
                # take before control returned to the graph?
                # ------------------------------------------------

                event_processing_ms = self._duration_ms(event_received_at)

                if event_processing_ms > 50:
                    logger.warning(
                        "[GRAPH_EVENT_SLOW] "
                        "session=%s "
                        "turn=%s "
                        "event=%d "
                        "processing_ms=%.2f "
                        "elapsed_ms=%.2f",
                        self.session_id,
                        turn_id,
                        event_id,
                        event_processing_ms,
                        self._elapsed_ms(),
                    )

            # ====================================================
            # Graph finished
            # ====================================================

            graph_duration = self._duration_ms(assistant_start)

            logger.info(
                "[GRAPH_STREAM_COMPLETE] "
                "session=%s "
                "turn=%s "
                "duration_ms=%.2f "
                "events=%d "
                "text_chars=%d "
                "remaining_buffer_chars=%d "
                "elapsed_ms=%.2f",
                self.session_id,
                turn_id,
                graph_duration,
                self._assistant_graph_events,
                len(total_text),
                len(sentence_buffer),
                self._elapsed_ms(),
            )

            if not self._assistant_is_current(
                turn_id,
                generation,
            ):
                return

            # ----------------------------------------------------
            # Final incomplete sentence.
            # ----------------------------------------------------

            remaining = sentence_buffer.strip()

            if remaining:
                logger.info(
                    "[FINAL_TEXT_BUFFER] "
                    "session=%s "
                    "turn=%s "
                    "text=%r "
                    "chars=%d "
                    "elapsed_ms=%.2f",
                    self.session_id,
                    turn_id,
                    remaining,
                    len(remaining),
                    self._elapsed_ms(),
                )

                success = await self._synthesize_sentence(
                    sentence=remaining,
                    turn_id=turn_id,
                    generation=generation,
                )

                if not success:
                    return

            # ====================================================
            # Assistant completed
            # ====================================================

            if not self._assistant_is_current(
                turn_id,
                generation,
            ):
                return

            logger.info(
                "[ASSISTANT_COMPLETED] "
                "session=%s "
                "turn=%s "
                "total_duration_ms=%.2f "
                "chars=%d "
                "graph_events=%d "
                "text_tokens=%d "
                "audio_chunks=%d "
                "audio_bytes=%d "
                "elapsed_ms=%.2f",
                self.session_id,
                turn_id,
                self._duration_ms(assistant_start),
                len(total_text),
                self._assistant_graph_events,
                self._assistant_text_tokens,
                self._assistant_audio_chunks,
                self._assistant_audio_bytes,
                self._elapsed_ms(),
            )

            if self.on_assistant_completed:
                callback_start = self._now()

                await self.on_assistant_completed(turn_id)

                logger.debug(
                    "[CALLBACK_DONE] "
                    "session=%s "
                    "callback=on_assistant_completed "
                    "turn=%s "
                    "duration_ms=%.2f "
                    "elapsed_ms=%.2f",
                    self.session_id,
                    turn_id,
                    self._duration_ms(callback_start),
                    self._elapsed_ms(),
                )

            self.assistant_turn_id = None

        except asyncio.CancelledError:
            logger.info(
                "[GRAPH_STREAM_CANCELLED] "
                "session=%s "
                "turn=%s "
                "duration_ms=%.2f "
                "elapsed_ms=%.2f",
                self.session_id,
                turn_id,
                self._duration_ms(assistant_start),
                self._elapsed_ms(),
            )

            raise

        except Exception:
            logger.exception(
                "[GRAPH_STREAM_ERROR] "
                "session=%s "
                "turn=%s "
                "duration_ms=%.2f "
                "elapsed_ms=%.2f",
                self.session_id,
                turn_id,
                self._duration_ms(assistant_start),
                self._elapsed_ms(),
            )

            raise

    # ========================================================
    # Assistant validity
    # ========================================================

    def _assistant_is_current(
        self,
        turn_id: int,
        generation: int,
    ) -> bool:
        """
        Determine whether an assistant operation still owns
        the output channel.
        """

        current = (
            self.running
            and generation == self._generation
            and self.assistant_turn_id == turn_id
        )

        if not current:
            logger.debug(
                "[ASSISTANT_NOT_CURRENT] "
                "session=%s "
                "requested_turn=%s "
                "current_turn=%s "
                "requested_generation=%d "
                "current_generation=%d "
                "running=%s "
                "elapsed_ms=%.2f",
                self.session_id,
                turn_id,
                self.assistant_turn_id,
                generation,
                self._generation,
                self.running,
                self._elapsed_ms(),
            )

        return current

    # ========================================================
    # Synthesize sentence
    # ========================================================

    async def _synthesize_sentence(
        self,
        sentence: str,
        turn_id: int,
        generation: int,
    ) -> bool:
        """
        Stream one buffered sentence through TTS.

        This is the current text buffering boundary:

            graph text
                ↓
            sentence_buffer
                ↓
            complete sentence
                ↓
            synthesize_stream()
                ↓
            audio chunks
        """

        sentence = sentence.strip()

        if not sentence:
            return True

        if not self._assistant_is_current(
            turn_id,
            generation,
        ):
            return False

        tts_start = self._now()

        logger.info(
            "[TTS_START] "
            "session=%s "
            "turn=%s "
            "generation=%d "
            "text=%r "
            "chars=%d "
            "elapsed_ms=%.2f",
            self.session_id,
            turn_id,
            generation,
            sentence,
            len(sentence),
            self._elapsed_ms(),
        )

        chunk_count = 0
        audio_bytes = 0

        try:
            async for audio in self.synthesizer.synthesize_stream(sentence):
                if not self._assistant_is_current(
                    turn_id,
                    generation,
                ):
                    logger.info(
                        "[TTS_STALE_AUDIO] session=%s turn=%s chunk=%d elapsed_ms=%.2f",
                        self.session_id,
                        turn_id,
                        chunk_count,
                        self._elapsed_ms(),
                    )

                    return False

                if not audio:
                    continue

                chunk_count += 1
                audio_bytes += len(audio)

                self._assistant_audio_chunks += 1
                self._assistant_audio_bytes += len(audio)

                logger.debug(
                    "[TTS_AUDIO_CHUNK] "
                    "session=%s "
                    "turn=%s "
                    "chunk=%d "
                    "bytes=%d "
                    "sentence_audio_bytes=%d "
                    "elapsed_ms=%.2f "
                    "tts_elapsed_ms=%.2f",
                    self.session_id,
                    turn_id,
                    chunk_count,
                    len(audio),
                    audio_bytes,
                    self._elapsed_ms(),
                    self._duration_ms(tts_start),
                )

                if self.on_assistant_audio:
                    callback_start = self._now()

                    await self.on_assistant_audio(
                        audio,
                        turn_id,
                    )

                    callback_duration = self._duration_ms(callback_start)

                    logger.debug(
                        "[FRONTEND_AUDIO_OUT] "
                        "session=%s "
                        "turn=%s "
                        "chunk=%d "
                        "bytes=%d "
                        "callback_ms=%.2f "
                        "elapsed_ms=%.2f",
                        self.session_id,
                        turn_id,
                        chunk_count,
                        len(audio),
                        callback_duration,
                        self._elapsed_ms(),
                    )

                    # ------------------------------------------------
                    # If the transport callback is slow, it can
                    # directly affect perceived voice latency.
                    # ------------------------------------------------

                    if callback_duration > 50:
                        logger.warning(
                            "[FRONTEND_AUDIO_SLOW] "
                            "session=%s "
                            "turn=%s "
                            "chunk=%d "
                            "callback_ms=%.2f "
                            "elapsed_ms=%.2f",
                            self.session_id,
                            turn_id,
                            chunk_count,
                            callback_duration,
                            self._elapsed_ms(),
                        )

            success = self._assistant_is_current(
                turn_id,
                generation,
            )

            logger.info(
                "[TTS_COMPLETE] "
                "session=%s "
                "turn=%s "
                "duration_ms=%.2f "
                "chunks=%d "
                "audio_bytes=%d "
                "success=%s "
                "elapsed_ms=%.2f",
                self.session_id,
                turn_id,
                self._duration_ms(tts_start),
                chunk_count,
                audio_bytes,
                success,
                self._elapsed_ms(),
            )

            return success

        except asyncio.CancelledError:
            logger.info(
                "[TTS_CANCELLED] "
                "session=%s "
                "turn=%s "
                "duration_ms=%.2f "
                "chunks=%d "
                "audio_bytes=%d "
                "elapsed_ms=%.2f",
                self.session_id,
                turn_id,
                self._duration_ms(tts_start),
                chunk_count,
                audio_bytes,
                self._elapsed_ms(),
            )

            raise

        except Exception:
            logger.exception(
                "[TTS_ERROR] "
                "session=%s "
                "turn=%s "
                "duration_ms=%.2f "
                "chunks=%d "
                "audio_bytes=%d "
                "elapsed_ms=%.2f",
                self.session_id,
                turn_id,
                self._duration_ms(tts_start),
                chunk_count,
                audio_bytes,
                self._elapsed_ms(),
            )

            raise

    # ========================================================
    # Interrupt assistant
    # ========================================================

    async def interrupt_assistant(
        self,
    ) -> None:
        """
        Interrupt the currently running assistant.

        Order:

            1. invalidate execution
            2. clear ownership
            3. cancel TTS
            4. cancel graph stream
        """

        old_turn_id = self.assistant_turn_id

        if old_turn_id is None:
            logger.debug(
                "[INTERRUPT_SKIP] "
                "session=%s "
                "reason=no_active_assistant "
                "elapsed_ms=%.2f",
                self.session_id,
                self._elapsed_ms(),
            )

            return

        interrupt_start = self._now()

        logger.info(
            "[INTERRUPT_START] session=%s turn=%s generation_before=%d elapsed_ms=%.2f",
            self.session_id,
            old_turn_id,
            self._generation,
            self._elapsed_ms(),
        )

        # ----------------------------------------------------
        # Invalidate output BEFORE cancellation.
        # ----------------------------------------------------

        self._generation += 1

        self.assistant_turn_id = None

        logger.info(
            "[INTERRUPT_INVALIDATED] "
            "session=%s "
            "old_turn=%s "
            "new_generation=%d "
            "elapsed_ms=%.2f",
            self.session_id,
            old_turn_id,
            self._generation,
            self._elapsed_ms(),
        )

        # ----------------------------------------------------
        # Stop TTS first.
        # ----------------------------------------------------

        tts_cancel_start = self._now()

        try:
            await self.synthesizer.cancel()

            logger.info(
                "[TTS_CANCEL_COMPLETE] "
                "session=%s "
                "turn=%s "
                "duration_ms=%.2f "
                "elapsed_ms=%.2f",
                self.session_id,
                old_turn_id,
                self._duration_ms(tts_cancel_start),
                self._elapsed_ms(),
            )

        except Exception:
            logger.exception(
                "[TTS_CANCEL_ERROR] session=%s turn=%s elapsed_ms=%.2f",
                self.session_id,
                old_turn_id,
                self._elapsed_ms(),
            )

        # ----------------------------------------------------
        # Cancel graph stream.
        # ----------------------------------------------------

        task = self.assistant_task

        self.assistant_task = None

        if task is not None and not task.done():
            graph_cancel_start = self._now()

            logger.info(
                "[GRAPH_CANCEL_START] session=%s turn=%s elapsed_ms=%.2f",
                self.session_id,
                old_turn_id,
                self._elapsed_ms(),
            )

            task.cancel()

            await asyncio.gather(
                task,
                return_exceptions=True,
            )

            logger.info(
                "[GRAPH_CANCEL_COMPLETE] "
                "session=%s "
                "turn=%s "
                "duration_ms=%.2f "
                "elapsed_ms=%.2f",
                self.session_id,
                old_turn_id,
                self._duration_ms(graph_cancel_start),
                self._elapsed_ms(),
            )

        logger.info(
            "[INTERRUPT_COMPLETE] "
            "session=%s "
            "turn=%s "
            "total_duration_ms=%.2f "
            "new_generation=%d "
            "elapsed_ms=%.2f",
            self.session_id,
            old_turn_id,
            self._duration_ms(interrupt_start),
            self._generation,
            self._elapsed_ms(),
        )

    # ========================================================
    # Cancel assistant
    # ========================================================

    async def cancel_assistant(
        self,
    ) -> None:
        """
        Cancel the active assistant execution.

        This does not cancel pending Whisper transcription.
        """

        cancel_start = self._now()

        old_turn_id = self.assistant_turn_id

        logger.info(
            "[ASSISTANT_CANCEL_START] "
            "session=%s "
            "turn=%s "
            "generation_before=%d "
            "elapsed_ms=%.2f",
            self.session_id,
            old_turn_id,
            self._generation,
            self._elapsed_ms(),
        )

        # ----------------------------------------------------
        # Invalidate current assistant output immediately.
        # ----------------------------------------------------

        self._generation += 1

        self.assistant_turn_id = None

        logger.debug(
            "[ASSISTANT_INVALIDATED] "
            "session=%s "
            "old_turn=%s "
            "generation=%d "
            "elapsed_ms=%.2f",
            self.session_id,
            old_turn_id,
            self._generation,
            self._elapsed_ms(),
        )

        # ----------------------------------------------------
        # Cancel TTS.
        # ----------------------------------------------------

        tts_cancel_start = self._now()

        try:
            await self.synthesizer.cancel()

            logger.debug(
                "[TTS_CANCEL_DONE] session=%s duration_ms=%.2f elapsed_ms=%.2f",
                self.session_id,
                self._duration_ms(tts_cancel_start),
                self._elapsed_ms(),
            )

        except Exception:
            logger.exception(
                "[TTS_CANCEL_ERROR] session=%s elapsed_ms=%.2f",
                self.session_id,
                self._elapsed_ms(),
            )

        # ----------------------------------------------------
        # Cancel graph stream.
        # ----------------------------------------------------

        task = self.assistant_task

        self.assistant_task = None

        if task is not None and not task.done():
            task.cancel()

            await asyncio.gather(
                task,
                return_exceptions=True,
            )

            logger.debug(
                "[GRAPH_CANCEL_DONE] session=%s turn=%s elapsed_ms=%.2f",
                self.session_id,
                old_turn_id,
                self._elapsed_ms(),
            )

        logger.info(
            "[ASSISTANT_CANCEL_COMPLETE] "
            "session=%s "
            "turn=%s "
            "duration_ms=%.2f "
            "generation=%d "
            "elapsed_ms=%.2f",
            self.session_id,
            old_turn_id,
            self._duration_ms(cancel_start),
            self._generation,
            self._elapsed_ms(),
        )

    # ========================================================
    # Close
    # ========================================================

    async def close(self) -> None:
        """
        Completely shut down the pipeline.

        Close is idempotent.
        """

        if self._closing:
            logger.debug(
                "[PIPELINE_CLOSE_SKIP] "
                "session=%s "
                "reason=already_closing "
                "elapsed_ms=%.2f",
                self.session_id,
                self._elapsed_ms(),
            )

            return

        self._closing = True

        if not self.running:
            logger.debug(
                "[PIPELINE_CLOSE_SKIP] session=%s reason=not_running elapsed_ms=%.2f",
                self.session_id,
                self._elapsed_ms(),
            )

            return

        close_start = self._now()

        logger.info(
            "[PIPELINE_CLOSE_START] session=%s generation=%d elapsed_ms=%.2f",
            self.session_id,
            self._generation,
            self._elapsed_ms(),
        )

        # ----------------------------------------------------
        # Stop accepting new audio immediately.
        # ----------------------------------------------------

        self.running = False

        self._generation += 1

        logger.debug(
            "[PIPELINE_INVALIDATED] session=%s generation=%d elapsed_ms=%.2f",
            self.session_id,
            self._generation,
            self._elapsed_ms(),
        )

        # ----------------------------------------------------
        # Cancel assistant + TTS.
        # ----------------------------------------------------

        await self.cancel_assistant()

        # ----------------------------------------------------
        # Cancel pending Whisper tasks.
        # ----------------------------------------------------

        transcription_tasks = list(self._speech_transcription_tasks)

        logger.info(
            "[WHISPER_SHUTDOWN] session=%s pending_tasks=%d elapsed_ms=%.2f",
            self.session_id,
            len(transcription_tasks),
            self._elapsed_ms(),
        )

        for task in transcription_tasks:
            if not task.done():
                task.cancel()

        if transcription_tasks:
            await asyncio.gather(
                *transcription_tasks,
                return_exceptions=True,
            )

        self._speech_transcription_tasks.clear()

        # ----------------------------------------------------
        # Reset VAD.
        # ----------------------------------------------------

        try:
            reset_start = self._now()

            self.vad.reset()

            logger.debug(
                "[VAD_RESET] session=%s duration_ms=%.2f elapsed_ms=%.2f",
                self.session_id,
                self._duration_ms(reset_start),
                self._elapsed_ms(),
            )

        except Exception:
            logger.exception(
                "[VAD_RESET_ERROR] session=%s elapsed_ms=%.2f",
                self.session_id,
                self._elapsed_ms(),
            )

        # ----------------------------------------------------
        # Reset conversational state.
        # ----------------------------------------------------

        try:
            reset_start = self._now()

            await self.turn_detector.reset()

            logger.debug(
                "[TURN_DETECTOR_RESET] session=%s duration_ms=%.2f elapsed_ms=%.2f",
                self.session_id,
                self._duration_ms(reset_start),
                self._elapsed_ms(),
            )

        except Exception:
            logger.exception(
                "[TURN_DETECTOR_RESET_ERROR] session=%s elapsed_ms=%.2f",
                self.session_id,
                self._elapsed_ms(),
            )

        # ----------------------------------------------------
        # Close decoder.
        # ----------------------------------------------------

        try:
            close_component_start = self._now()

            await self.decoder.close()

            logger.debug(
                "[DECODER_CLOSED] session=%s duration_ms=%.2f elapsed_ms=%.2f",
                self.session_id,
                self._duration_ms(close_component_start),
                self._elapsed_ms(),
            )

        except Exception:
            logger.exception(
                "[DECODER_CLOSE_ERROR] session=%s elapsed_ms=%.2f",
                self.session_id,
                self._elapsed_ms(),
            )

        # ----------------------------------------------------
        # Close TTS.
        # ----------------------------------------------------

        try:
            close_component_start = self._now()

            await self.synthesizer.close()

            logger.debug(
                "[SYNTHESIZER_CLOSED] session=%s duration_ms=%.2f elapsed_ms=%.2f",
                self.session_id,
                self._duration_ms(close_component_start),
                self._elapsed_ms(),
            )

        except Exception:
            logger.exception(
                "[SYNTHESIZER_CLOSE_ERROR] session=%s elapsed_ms=%.2f",
                self.session_id,
                self._elapsed_ms(),
            )

        logger.info(
            "[PIPELINE_CLOSED] "
            "session=%s "
            "total_close_ms=%.2f "
            "received_chunks=%d "
            "received_bytes=%d "
            "decoded_frames=%d "
            "decoded_pcm_bytes=%d "
            "elapsed_ms=%.2f",
            self.session_id,
            self._duration_ms(close_start),
            self._received_audio_chunks,
            self._received_audio_bytes,
            self._decoded_frames,
            self._decoded_pcm_bytes,
            self._elapsed_ms(),
        )
