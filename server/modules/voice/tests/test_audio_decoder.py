# python -m pytest modules\voice\tests\test_audio_decoder.py -v
import asyncio
import io

import av
import numpy as np

from modules.voice.audio_decoder import AudioDecoder


SAMPLE_RATE = 16000
FRAME_DURATION_MS = 20
SAMPLES_PER_FRAME = (
    SAMPLE_RATE * FRAME_DURATION_MS // 1000
)


def create_webm_audio(
    duration_seconds: float = 0.1,
    sample_rate: int = 48000,
) -> bytes:
    """
    Generate a valid WebM/Opus audio stream using PyAV.
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

    total_samples = int(
        sample_rate * duration_seconds
    )

    samples_per_frame = 960

    for start in range(
        0,
        total_samples,
        samples_per_frame,
    ):

        count = min(
            samples_per_frame,
            total_samples - start,
        )

        samples = np.zeros(
            count,
            dtype=np.int16,
        )

        frame = av.AudioFrame.from_ndarray(
            samples.reshape(1, -1),
            format="s16",
            layout="mono",
        )

        frame.sample_rate = sample_rate

        for packet in stream.encode(frame):
            container.mux(packet)

    for packet in stream.encode():
        container.mux(packet)

    container.close()

    return output.getvalue()


def test_decoder_returns_pcm_frames():

    async def run():

        decoder = AudioDecoder(
            sample_rate=SAMPLE_RATE,
            frame_duration_ms=FRAME_DURATION_MS,
        )

        webm = create_webm_audio(
            duration_seconds=0.1,
        )

        frames = await decoder.decode(webm)

        assert frames

        for frame in frames:

            assert isinstance(
                frame,
                bytes,
            )

            assert len(frame) == (
                SAMPLES_PER_FRAME * 2
            )

        await decoder.close()

    asyncio.run(run())


def test_decoder_produces_pcm16_mono():

    async def run():

        decoder = AudioDecoder(
            sample_rate=SAMPLE_RATE,
            frame_duration_ms=FRAME_DURATION_MS,
        )

        webm = create_webm_audio(
            duration_seconds=0.1,
        )

        frames = await decoder.decode(webm)

        assert frames

        pcm = np.frombuffer(
            frames[0],
            dtype=np.int16,
        )

        assert pcm.dtype == np.int16

        assert len(pcm) == SAMPLES_PER_FRAME

        await decoder.close()

    asyncio.run(run())


def test_decoder_buffers_partial_frame():

    async def run():

        decoder = AudioDecoder(
            sample_rate=SAMPLE_RATE,
            frame_duration_ms=FRAME_DURATION_MS,
        )

        webm = create_webm_audio(
            duration_seconds=0.025,
        )

        frames = await decoder.decode(webm)

        for frame in frames:

            assert len(frame) == (
                SAMPLES_PER_FRAME * 2
            )

        assert (
            decoder.buffered_bytes
            < SAMPLES_PER_FRAME * 2
        )

        await decoder.close()

    asyncio.run(run())


def test_flush_returns_remaining_audio():

    async def run():

        decoder = AudioDecoder(
            sample_rate=SAMPLE_RATE,
            frame_duration_ms=FRAME_DURATION_MS,
        )

        webm = create_webm_audio(
            duration_seconds=0.025,
        )

        await decoder.decode(webm)

        remaining = await decoder.flush()

        for frame in remaining:

            assert isinstance(
                frame,
                bytes,
            )

            assert len(frame) > 0

            assert len(frame) <= (
                SAMPLES_PER_FRAME * 2
            )

        assert decoder.buffered_bytes == 0

        await decoder.close()

    asyncio.run(run())


def test_empty_chunk_returns_no_frames():

    async def run():

        decoder = AudioDecoder(
            sample_rate=SAMPLE_RATE,
            frame_duration_ms=FRAME_DURATION_MS,
        )

        frames = await decoder.decode(b"")

        assert frames == []

        await decoder.close()

    asyncio.run(run())


def test_reset_clears_buffer():

    async def run():

        decoder = AudioDecoder(
            sample_rate=SAMPLE_RATE,
            frame_duration_ms=FRAME_DURATION_MS,
        )

        webm = create_webm_audio(
            duration_seconds=0.025,
        )

        await decoder.decode(webm)

        await decoder.reset()

        assert decoder.buffered_bytes == 0

        await decoder.close()

    asyncio.run(run())


def test_decode_after_close_raises():

    async def run():

        decoder = AudioDecoder(
            sample_rate=SAMPLE_RATE,
            frame_duration_ms=FRAME_DURATION_MS,
        )

        await decoder.close()

        try:

            await decoder.decode(
                b"some audio",
            )

        except RuntimeError as exc:

            assert "closed" in str(
                exc
            ).lower()

        else:

            assert False, (
                "decode() should raise "
                "after decoder is closed"
            )

    asyncio.run(run())