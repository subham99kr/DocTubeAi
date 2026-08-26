# python -m pytest modules\voice\tests\test_turn_detector.py -v

import pytest

from modules.voice.models import (
    SpeechStarted,
    TranscriptChanged,
    TurnCompleted,
)

from modules.voice.turn_detector import (
    TurnDetector,
)

from modules.voice.vad import (
    VADEvent,
    VADEventType,
)


# ============================================================
# Helpers
# ============================================================


def speech_started_event() -> VADEvent:
    return VADEvent(
        type=VADEventType.SPEECH_STARTED,
        speech_duration=0.20,
        audio=b"speech",
    )


def speech_ended_event() -> VADEvent:
    return VADEvent(
        type=VADEventType.SPEECH_ENDED,
        speech_duration=0.50,
        audio=b"speech",
    )


# ============================================================
# Speech started
# ============================================================


@pytest.mark.anyio
async def test_speech_started_creates_new_turn():

    detector = TurnDetector()

    events = await detector.process_vad_event(
        speech_started_event()
    )

    assert len(events) == 1

    assert isinstance(
        events[0],
        SpeechStarted,
    )

    assert events[0].turn_id == 1

    assert detector.active is True

    assert detector.turn_id == 1


# ============================================================
# Duplicate speech started
# ============================================================


@pytest.mark.anyio
async def test_duplicate_speech_started_is_ignored():

    detector = TurnDetector()

    first_events = await detector.process_vad_event(
        speech_started_event()
    )

    second_events = await detector.process_vad_event(
        speech_started_event()
    )

    assert len(first_events) == 1

    assert second_events == []

    assert detector.turn_id == 1

    assert detector.active is True


# ============================================================
# Transcript
# ============================================================


@pytest.mark.anyio
async def test_transcript_requires_active_turn():

    detector = TurnDetector()

    events = await detector.process_transcript(
        "hello"
    )

    assert events == []

    assert detector.active is False


@pytest.mark.anyio
async def test_transcript_creates_transcript_changed():

    detector = TurnDetector()

    await detector.process_vad_event(
        speech_started_event()
    )

    events = await detector.process_transcript(
        "hello"
    )

    assert len(events) == 1

    assert isinstance(
        events[0],
        TranscriptChanged,
    )

    assert events[0].turn_id == 1

    assert events[0].text == "hello"

    assert (
        detector.current_transcript
        == "hello"
    )


@pytest.mark.anyio
async def test_duplicate_transcript_is_ignored():

    detector = TurnDetector()

    await detector.process_vad_event(
        speech_started_event()
    )

    first_events = await detector.process_transcript(
        "hello"
    )

    second_events = await detector.process_transcript(
        "hello"
    )

    assert len(first_events) == 1

    assert second_events == []


# ============================================================
# Turn completion
# ============================================================


@pytest.mark.anyio
async def test_speech_end_completes_turn():

    detector = TurnDetector()

    await detector.process_vad_event(
        speech_started_event()
    )

    await detector.process_transcript(
        "hello world"
    )

    events = await detector.process_vad_event(
        speech_ended_event()
    )

    assert len(events) == 1

    assert isinstance(
        events[0],
        TurnCompleted,
    )

    assert events[0].turn_id == 1

    assert events[0].text == "hello world"

    assert detector.active is False

    assert detector.current_transcript == ""


# ============================================================
# Empty turn
# ============================================================


@pytest.mark.anyio
async def test_empty_speech_turn_is_discarded():

    detector = TurnDetector()

    await detector.process_vad_event(
        speech_started_event()
    )

    events = await detector.process_vad_event(
        speech_ended_event()
    )

    assert events == []

    assert detector.active is False

    assert detector.current_transcript == ""


# ============================================================
# Multiple turns
# ============================================================


@pytest.mark.anyio
async def test_multiple_turns_get_unique_ids():

    detector = TurnDetector()

    # --------------------------------------------------------
    # Turn 1
    # --------------------------------------------------------

    events = await detector.process_vad_event(
        speech_started_event()
    )

    assert events[0].turn_id == 1

    await detector.process_transcript(
        "first question"
    )

    events = await detector.process_vad_event(
        speech_ended_event()
    )

    assert isinstance(
        events[0],
        TurnCompleted,
    )

    assert events[0].turn_id == 1

    # --------------------------------------------------------
    # Turn 2
    # --------------------------------------------------------

    events = await detector.process_vad_event(
        speech_started_event()
    )

    assert events[0].turn_id == 2

    await detector.process_transcript(
        "second question"
    )

    events = await detector.process_vad_event(
        speech_ended_event()
    )

    assert isinstance(
        events[0],
        TurnCompleted,
    )

    assert events[0].turn_id == 2

    assert detector.turn_id == 2


# ============================================================
# Reset
# ============================================================


@pytest.mark.anyio
async def test_reset_clears_active_turn():

    detector = TurnDetector()

    await detector.process_vad_event(
        speech_started_event()
    )

    await detector.process_transcript(
        "hello"
    )

    assert detector.active is True

    await detector.reset()

    assert detector.active is False

    assert detector.turn_id == 0

    assert detector.current_transcript == ""