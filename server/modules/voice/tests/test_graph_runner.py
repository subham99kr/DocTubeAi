"""
Tests for VoiceGraphRunner.

Run from server/:

    python -m modules.voice.tests.test_graph_runner
"""

from __future__ import annotations

import asyncio


# ============================================================
# Test configuration
# ============================================================

SESSION_ID = "voice-test-session"

TEST_TEXT = (
    "What is Kubernetes and why is it useful?"
)


# ============================================================
# Test
# ============================================================


async def main() -> None:

    print()
    print("=" * 60)
    print("VOICE GRAPH RUNNER TEST")
    print("=" * 60)
    print()

    # --------------------------------------------------------
    # Import only after the Selector loop is running.
    # --------------------------------------------------------

    from modules.voice.graph_runner import (
        VoiceGraphRunner,
    )

    runner = VoiceGraphRunner()

    # ========================================================
    # Normal execution
    # ========================================================

    print("[1/2] Testing graph.run()...")
    print()

    response = await runner.run(
        text=TEST_TEXT,
        session_id=SESSION_ID,
    )

    print()
    print("-" * 60)
    print("NORMAL RESPONSE")
    print("-" * 60)
    print(response)
    print("-" * 60)
    print()

    if not response:
        raise RuntimeError(
            "graph.run() returned an empty response."
        )

    print("✅ graph.run() passed")
    print()

    # ========================================================
    # Streaming execution
    # ========================================================

    print("[2/2] Testing graph.stream()...")
    print()

    token_count = 0
    collected: list[str] = []

    async for token in runner.stream(
        text=TEST_TEXT,
        session_id=SESSION_ID,
    ):

        token_count += 1
        collected.append(token)

        print(
            token,
            end="",
            flush=True,
        )

    print()
    print()
    print("-" * 60)
    print("STREAMING RESULT")
    print("-" * 60)
    print("".join(collected))
    print("-" * 60)
    print()

    if token_count == 0:
        raise RuntimeError(
            "graph.stream() produced zero tokens."
        )

    print(
        f"✅ graph.stream() passed "
        f"({token_count} chunks)"
    )

    print()
    print("=" * 60)
    print("ALL GRAPH RUNNER TESTS PASSED")
    print("=" * 60)
    print()


# ============================================================
# Entry point
# ============================================================


if __name__ == "__main__":

    # --------------------------------------------------------
    # Psycopg on Windows requires SelectorEventLoop.
    #
    # Create the loop explicitly before main() starts.
    # --------------------------------------------------------

    loop = asyncio.SelectorEventLoop()

    try:

        asyncio.set_event_loop(loop)

        loop.run_until_complete(
            main()
        )

    finally:

        loop.run_until_complete(
            loop.shutdown_asyncgens()
        )

        loop.close()