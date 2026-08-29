"""
Tests for VoiceAssistant.

Run from server/:

    python -m modules.voice.tests.test_assistant
"""

from __future__ import annotations

import asyncio
import sys

from modules.voice.assistant import VoiceAssistant

# ============================================================
# Fake runner
# ============================================================


async def fake_runner(
    text: str,
    session_id: str,
) -> str:

    await asyncio.sleep(0.05)

    return (
        f"Assistant response to: {text}"
    )


# ============================================================
# Slow runner
# ============================================================


async def slow_runner(
    text: str,
    session_id: str,
) -> str:

    await asyncio.sleep(10)

    return "This should never complete."


# ============================================================
# Test normal execution
# ============================================================


async def test_normal_execution() -> None:

    print()
    print("[1/4] Testing normal execution...")

    assistant = VoiceAssistant(
        runner=fake_runner,
        timeout_seconds=5,
    )

    response = await assistant.start(
        "What is Kubernetes?",
        "test-session",
    )

    assert response == (
        "Assistant response to: "
        "What is Kubernetes?"
    )

    assert not assistant.running

    await assistant.close()

    print("✅ Normal execution passed")


# ============================================================
# Test empty input
# ============================================================


async def test_empty_input() -> None:

    print()
    print("[2/4] Testing empty input...")

    assistant = VoiceAssistant(
        runner=fake_runner,
    )

    response = await assistant.start(
        "   ",
        "test-session",
    )

    assert response is None

    await assistant.close()

    print("✅ Empty input passed")


# ============================================================
# Test cancellation
# ============================================================


async def test_cancellation() -> None:

    print()
    print("[3/4] Testing cancellation...")

    assistant = VoiceAssistant(
        runner=slow_runner,
        timeout_seconds=20,
    )

    task = asyncio.create_task(
        assistant.start(
            "This request will be cancelled.",
            "test-session",
        )
    )

    # Give the assistant enough time to start.
    await asyncio.sleep(0.1)

    assert assistant.running

    await assistant.cancel()

    result = await task

    assert result is None
    assert not assistant.running

    await assistant.close()

    print("✅ Cancellation passed")


# ============================================================
# Test timeout
# ============================================================


async def test_timeout() -> None:

    print()
    print("[4/4] Testing timeout...")

    assistant = VoiceAssistant(
        runner=slow_runner,
        timeout_seconds=0.1,
    )

    try:

        await assistant.start(
            "This request should timeout.",
            "test-session",
        )

    except asyncio.TimeoutError:

        print("✅ Timeout passed")

    else:

        raise AssertionError(
            "Expected asyncio.TimeoutError."
        )

    finally:

        await assistant.close()


# ============================================================
# Main
# ============================================================


async def main() -> None:

    print()
    print("=" * 60)
    print("VOICE ASSISTANT TEST")
    print("=" * 60)

    await test_normal_execution()

    await test_empty_input()

    await test_cancellation()

    await test_timeout()

    print()
    print("=" * 60)
    print("ALL ASSISTANT TESTS PASSED")
    print("=" * 60)
    print()


# ============================================================
# Entry point
# ============================================================


if __name__ == "__main__":

    if (
        sys.platform == "win32"
        and sys.version_info >= (3, 14)
    ):
        asyncio.run(
            main(),
            loop_factory=asyncio.SelectorEventLoop,
        )

    else:
        asyncio.run(main())