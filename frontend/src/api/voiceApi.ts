import axios from "axios";

const BACKEND_URL =
  import.meta.env.VITE_PUBLIC_BACKEND_URL ||
  import.meta.env.VITE_BACKEND_URL ||
  "http://127.0.0.1:8000";

/**
 * Response returned by the backend
 * after audio transcription.
 */
export type VoiceTranscriptionResponse = {
  transcript: string;
};

/**
 * Send recorded audio to the backend
 * for speech-to-text transcription.
 */
export async function transcribeAudio(
  audioBlob: Blob
): Promise<VoiceTranscriptionResponse> {
  const formData = new FormData();

  /*
   * Give the uploaded audio a filename.
   *
   * Whisper/FastAPI can use the file
   * extension to identify the format.
   */
  formData.append(
    "audio",
    audioBlob,
    "voice.webm"
  );

  const response =
    await axios.post<VoiceTranscriptionResponse>(
      `${BACKEND_URL}/voice/transcribe`,
      formData,
      {
        /*
         * Voice recordings can take some
         * time to upload/transcribe.
         */
        timeout: 120000,
      }
    );

  return response.data;
}