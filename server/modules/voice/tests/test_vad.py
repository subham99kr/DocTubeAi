import math

from modules.voice.vad import (
    VADEventType,
    VoiceActivityDetector,
)

SAMPLE_RATE = 16000
FRAME_DURATION_MS = 20

SAMPLES_PER_FRAME = (
    SAMPLE_RATE
    * FRAME_DURATION_MS
    // 1000
)


def make_pcm_frame(
    amplitude: int,
    samples: int = SAMPLES_PER_FRAME,
) -> bytes:
    """
    Generate a synthetic PCM16 mono frame.

    amplitude=0:
        silence

    amplitude>0:
        synthetic speech-like signal
    """

    pcm = bytearray()

    frequency = 440.0

    for i in range(samples):

        value = int(
            amplitude
            * math.sin(
                2.0
                * math.pi
                * frequency
                * i
                / SAMPLE_RATE
            )
        )

        value = max(
            -32768,
            min(32767, value),
        )

        pcm.extend(
            value.to_bytes(
                2,
                byteorder="little",
                signed=True,
            )
        )

    return bytes(pcm)


# ============================================================
# Silence
# ============================================================


def test_silence_produces_no_events():
    """
    Silence must not create speech events.
    """

    vad = VoiceActivityDetector(
        sample_rate=SAMPLE_RATE,
        frame_duration_ms=FRAME_DURATION_MS,
        energy_threshold=0.01,
        min_speech_seconds=0.15,
        silence_seconds=0.50,
    )

    silence = make_pcm_frame(0)

    events = []

    for _ in range(30):
        events.extend(
            vad.process(silence)
        )

    assert events == []

    assert vad.speaking is False


# ============================================================
# Speech start
# ============================================================


def test_speech_starts():
    """
    Sustained speech should produce SPEECH_STARTED
    once the minimum speech duration is reached.
    """

    vad = VoiceActivityDetector(
        sample_rate=SAMPLE_RATE,
        frame_duration_ms=FRAME_DURATION_MS,
        energy_threshold=0.01,
        min_speech_seconds=0.15,
        silence_seconds=0.50,
    )

    speech = make_pcm_frame(5000)

    events = []

    # 160 ms of speech.
    #
    # Each frame = 20 ms.
    #
    # 8 × 20 ms = 160 ms
    #
    # This crosses the 150 ms minimum.
    for _ in range(8):

        events.extend(
            vad.process(speech)
        )

    start_events = [
        event
        for event in events
        if event.type
        == VADEventType.SPEECH_STARTED
    ]

    assert len(start_events) == 1

    assert (
        start_events[0].speech_duration
        >= 0.15
    )

    assert vad.speaking is True


# ============================================================
# Speech end
# ============================================================


def test_speech_then_silence_ends():
    """
    Speech followed by sufficient silence should produce
    SPEECH_ENDED.
    """

    vad = VoiceActivityDetector(
        sample_rate=SAMPLE_RATE,
        frame_duration_ms=FRAME_DURATION_MS,
        energy_threshold=0.01,
        min_speech_seconds=0.15,
        silence_seconds=0.50,
    )

    speech = make_pcm_frame(5000)
    silence = make_pcm_frame(0)

    events = []

    # 500 ms speech.
    for _ in range(25):

        events.extend(
            vad.process(speech)
        )

    start_events = [
        event
        for event in events
        if event.type
        == VADEventType.SPEECH_STARTED
    ]

    assert len(start_events) == 1

    # 500 ms silence.
    end_events = []

    for _ in range(25):

        end_events.extend(
            vad.process(silence)
        )

    assert len(end_events) == 1

    assert (
        end_events[0].type
        == VADEventType.SPEECH_ENDED
    )

    assert (
        end_events[0].speech_duration
        >= 0.15
    )

    assert end_events[0].audio

    assert vad.speaking is False


# ============================================================
# Short noise
# ============================================================


def test_short_noise_is_discarded():
    """
    Very short audio below the minimum speech duration
    should not produce SPEECH_ENDED.
    """

    vad = VoiceActivityDetector(
        sample_rate=SAMPLE_RATE,
        frame_duration_ms=FRAME_DURATION_MS,
        energy_threshold=0.01,
        min_speech_seconds=0.15,
        silence_seconds=0.50,
    )

    noise = make_pcm_frame(5000)
    silence = make_pcm_frame(0)

    events = []

    # 100 ms of audio.
    #
    # 5 × 20 ms = 100 ms
    #
    # This is below the 150 ms minimum.
    for _ in range(5):

        events.extend(
            vad.process(noise)
        )

    # Enough silence to allow the VAD to decide
    # whether the candidate was a real speech segment.
    for _ in range(25):

        events.extend(
            vad.process(silence)
        )

    end_events = [
        event
        for event in events
        if event.type
        == VADEventType.SPEECH_ENDED
    ]

    assert end_events == []

    assert vad.speaking is False


# ============================================================
# Short pause
# ============================================================


def test_speech_can_resume_after_short_pause():
    """
    A pause shorter than silence_seconds should not end
    the speech segment.
    """

    vad = VoiceActivityDetector(
        sample_rate=SAMPLE_RATE,
        frame_duration_ms=FRAME_DURATION_MS,
        energy_threshold=0.01,
        min_speech_seconds=0.15,
        silence_seconds=0.50,
    )

    speech = make_pcm_frame(5000)
    silence = make_pcm_frame(0)

    events = []

    # 300 ms speech.
    #
    # 15 × 20 ms = 300 ms.
    for _ in range(15):

        events.extend(
            vad.process(speech)
        )

    # 200 ms pause.
    #
    # This is shorter than the 500 ms silence
    # required to end the speech segment.
    for _ in range(10):

        events.extend(
            vad.process(silence)
        )

    # Speech resumes.
    for _ in range(15):

        events.extend(
            vad.process(speech)
        )

    end_events = [
        event
        for event in events
        if event.type
        == VADEventType.SPEECH_ENDED
    ]

    assert end_events == []

    assert vad.speaking is True