from faster_whisper import WhisperModel


class VoiceTranscriber:
    def __init__(
        self,
        model_size: str = "base",
    ):
        print(
            f"🎙 Loading Whisper model: {model_size}"
        )

        self.model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
        )

        print(
            "✅ Whisper model loaded"
        )

    def transcribe(
        self,
        audio_path: str,
    ) -> str:

        print(
            f"🎙 Transcribing: {audio_path}"
        )

        segments, info = self.model.transcribe(
            audio_path,
            language="en",
            beam_size=5,
            vad_filter=True,
        )

        transcript_parts = []

        for segment in segments:
            text = segment.text.strip()

            if text:
                transcript_parts.append(text)

        transcript = " ".join(
            transcript_parts
        ).strip()

        print(
            f"📝 Transcript: {transcript}"
        )

        return transcript


# Load the model once when the application starts.
transcriber = VoiceTranscriber(
    model_size="base"
)