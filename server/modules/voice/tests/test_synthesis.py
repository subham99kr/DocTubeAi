import asyncio

from modules.voice.synthesis import speech_synthesizer


async def main():

    synthesizer = speech_synthesizer()

    await synthesizer.start()

    result = await synthesizer.synthesize(
        "Hello. This is a test of the DocTubeAI voice pipeline."
    )

    if result is None:
        print("❌ No synthesis result")
        return

    print("✅ Synthesis successful")
    print("Format:", result.format)
    print("Bytes:", len(result.audio))
    print("Has audio:", result.has_audio)

    with open(
        "test_output.mp3",
        "wb",
    ) as file:
        file.write(result.audio)

    await synthesizer.close()


if __name__ == "__main__":
    asyncio.run(main())