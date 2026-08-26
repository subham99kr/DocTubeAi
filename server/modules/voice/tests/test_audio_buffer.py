# python -m pytest modules\voice\tests\test_audio_buffer.py -v
import os

import pytest

from modules.voice.audio_buffer import AudioBuffer
from modules.voice.config import (
    MAX_AUDIO_BYTES,
    MIN_AUDIO_BYTES,
)


# ============================================================
# Helpers
# ============================================================


def make_audio(
    size: int,
) -> bytes:
    """
    Generate deterministic fake PCM/audio bytes.
    """

    return bytes(
        (i % 256 for i in range(size))
    )


# ============================================================
# Start
# ============================================================


@pytest.mark.anyio
async def test_audio_buffer_starts():

    buffer = AudioBuffer()

    await buffer.start()

    assert buffer.closed is False
    assert buffer.audio_path is not None
    assert buffer.audio_bytes == 0
    assert buffer.has_audio is False

    await buffer.close()


@pytest.mark.anyio
async def test_start_is_idempotent():

    buffer = AudioBuffer()

    await buffer.start()

    first_path = buffer.audio_path

    await buffer.start()

    assert buffer.audio_path == first_path
    assert buffer.audio_bytes == 0

    await buffer.close()


# ============================================================
# Append
# ============================================================


@pytest.mark.anyio
async def test_append_audio():

    buffer = AudioBuffer()

    await buffer.start()

    audio = make_audio(
        MIN_AUDIO_BYTES
    )

    await buffer.append(audio)

    assert buffer.audio_bytes == len(audio)
    assert buffer.has_audio is True

    await buffer.close()


@pytest.mark.anyio
async def test_append_empty_audio_is_ignored():

    buffer = AudioBuffer()

    await buffer.start()

    await buffer.append(b"")

    assert buffer.audio_bytes == 0
    assert buffer.has_audio is False

    await buffer.close()


@pytest.mark.anyio
async def test_multiple_audio_chunks_are_buffered():

    buffer = AudioBuffer()

    await buffer.start()

    chunk1 = make_audio(1000)
    chunk2 = make_audio(2000)
    chunk3 = make_audio(
        MIN_AUDIO_BYTES
        - len(chunk1)
        - len(chunk2)
    )

    await buffer.append(chunk1)
    await buffer.append(chunk2)
    await buffer.append(chunk3)

    expected_size = (
        len(chunk1)
        + len(chunk2)
        + len(chunk3)
    )

    assert buffer.audio_bytes == expected_size
    assert buffer.has_audio is True

    await buffer.close()


# ============================================================
# Snapshot
# ============================================================


@pytest.mark.anyio
async def test_snapshot_requires_minimum_audio():

    buffer = AudioBuffer()

    await buffer.start()

    audio = make_audio(
        max(1, MIN_AUDIO_BYTES - 1)
    )

    await buffer.append(audio)

    snapshot = await buffer.snapshot()

    assert snapshot is None

    await buffer.close()


@pytest.mark.anyio
async def test_snapshot_returns_independent_file():

    buffer = AudioBuffer()

    await buffer.start()

    audio = make_audio(
        MIN_AUDIO_BYTES
    )

    await buffer.append(audio)

    snapshot = await buffer.snapshot()

    assert snapshot is not None
    assert os.path.exists(snapshot)

    with open(
        snapshot,
        "rb",
    ) as file:

        snapshot_data = file.read()

    assert snapshot_data == audio

    buffer.delete_snapshot(snapshot)

    assert not os.path.exists(snapshot)

    await buffer.close()


@pytest.mark.anyio
async def test_snapshot_does_not_clear_buffer():

    buffer = AudioBuffer()

    await buffer.start()

    audio = make_audio(
        MIN_AUDIO_BYTES
    )

    await buffer.append(audio)

    snapshot1 = await buffer.snapshot()

    assert snapshot1 is not None

    assert buffer.audio_bytes == len(audio)
    assert buffer.has_audio is True

    snapshot2 = await buffer.snapshot()

    assert snapshot2 is not None
    assert snapshot2 != snapshot1

    buffer.delete_snapshot(snapshot1)
    buffer.delete_snapshot(snapshot2)

    await buffer.close()


# ============================================================
# Maximum size
# ============================================================


@pytest.mark.anyio
async def test_append_cannot_exceed_maximum_audio_size():

    buffer = AudioBuffer()

    await buffer.start()

    audio = make_audio(
        MAX_AUDIO_BYTES + 1
    )

    with pytest.raises(
        ValueError,
        match="Maximum voice audio size exceeded",
    ):

        await buffer.append(audio)

    assert buffer.audio_bytes == 0

    await buffer.close()


@pytest.mark.anyio
async def test_append_exact_maximum_size_is_allowed():

    buffer = AudioBuffer()

    await buffer.start()

    audio = make_audio(
        MAX_AUDIO_BYTES
    )

    await buffer.append(audio)

    assert buffer.audio_bytes == (
        MAX_AUDIO_BYTES
    )

    await buffer.close()


# ============================================================
# Reset
# ============================================================


@pytest.mark.anyio
async def test_reset_clears_buffer():

    buffer = AudioBuffer()

    await buffer.start()

    audio = make_audio(
        MIN_AUDIO_BYTES
    )

    await buffer.append(audio)

    old_path = buffer.audio_path

    assert old_path is not None
    assert os.path.exists(old_path)

    await buffer.reset()

    assert buffer.audio_bytes == 0
    assert buffer.has_audio is False
    assert buffer.audio_path is not None
    assert buffer.audio_path != old_path
    assert os.path.exists(buffer.audio_path)

    assert not os.path.exists(old_path)

    await buffer.close()


@pytest.mark.anyio
async def test_buffer_can_be_reused_after_reset():

    buffer = AudioBuffer()

    await buffer.start()

    first_audio = make_audio(
        MIN_AUDIO_BYTES
    )

    await buffer.append(first_audio)

    await buffer.reset()

    second_audio = make_audio(
        MIN_AUDIO_BYTES
    )

    await buffer.append(second_audio)

    assert buffer.audio_bytes == (
        len(second_audio)
    )

    snapshot = await buffer.snapshot()

    assert snapshot is not None

    with open(
        snapshot,
        "rb",
    ) as file:

        data = file.read()

    assert data == second_audio

    buffer.delete_snapshot(snapshot)

    await buffer.close()


# ============================================================
# Lifecycle errors
# ============================================================


@pytest.mark.anyio
async def test_append_before_start_is_rejected():

    buffer = AudioBuffer()

    with pytest.raises(
        RuntimeError,
        match="has not been started",
    ):

        await buffer.append(
            b"\x01\x02"
        )


@pytest.mark.anyio
async def test_snapshot_before_start_returns_none():

    buffer = AudioBuffer()

    snapshot = await buffer.snapshot()

    assert snapshot is None


@pytest.mark.anyio
async def test_append_after_close_is_rejected():

    buffer = AudioBuffer()

    await buffer.start()
    await buffer.close()

    with pytest.raises(
        RuntimeError,
        match="closed",
    ):

        await buffer.append(
            b"\x01\x02"
        )


@pytest.mark.anyio
async def test_start_after_close_is_rejected():

    buffer = AudioBuffer()

    await buffer.start()
    await buffer.close()

    with pytest.raises(
        RuntimeError,
        match="closed",
    ):

        await buffer.start()


@pytest.mark.anyio
async def test_snapshot_after_close_returns_none():

    buffer = AudioBuffer()

    await buffer.start()

    audio = make_audio(
        MIN_AUDIO_BYTES
    )

    await buffer.append(audio)

    await buffer.close()

    snapshot = await buffer.snapshot()

    assert snapshot is None


# ============================================================
# Delete snapshot
# ============================================================


def test_delete_snapshot_none_is_safe():

    AudioBuffer.delete_snapshot(None)


def test_delete_snapshot_missing_file_is_safe():

    AudioBuffer.delete_snapshot(
        "this_file_does_not_exist.wav"
    )


# ============================================================
# Close
# ============================================================


@pytest.mark.anyio
async def test_close_deletes_active_recording():

    buffer = AudioBuffer()

    await buffer.start()

    path = buffer.audio_path

    assert path is not None
    assert os.path.exists(path)

    await buffer.close()

    assert buffer.closed is True
    assert buffer.audio_path is None
    assert buffer.audio_bytes == 0
    assert buffer.has_audio is False

    assert not os.path.exists(path)


@pytest.mark.anyio
async def test_close_is_idempotent():

    buffer = AudioBuffer()

    await buffer.start()

    await buffer.close()
    await buffer.close()

    assert buffer.closed is True
    assert buffer.audio_path is None