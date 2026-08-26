export type VoiceRecorderCallbacks = {
  onStart?: () => void;

  onChunk?: (
    chunk: Blob
  ) => void;

  onStop?: (
    audioBlob: Blob
  ) => void;

  onError?: (
    error: Error
  ) => void;
};

export class VoiceRecorderService {
  private mediaRecorder: MediaRecorder | null =
    null;

  private audioChunks: Blob[] = [];

  private stream: MediaStream | null =
    null;

  private stoppingManually = false;

  async start(
    callbacks: VoiceRecorderCallbacks = {}
  ): Promise<void> {
    try {
      this.stoppingManually = false;

      /*
       * Ask browser for microphone permission.
       */
      this.stream =
        await navigator.mediaDevices.getUserMedia(
          {
            audio: true,
          }
        );

      this.audioChunks = [];

      /*
       * Let the browser choose a supported
       * audio format.
       */
      const mimeType =
        this.getSupportedMimeType();

      this.mediaRecorder = mimeType
        ? new MediaRecorder(
            this.stream,
            {
              mimeType,
            }
          )
        : new MediaRecorder(
            this.stream
          );

      this.mediaRecorder.onstart = () => {
        console.log(
          "🎙 MediaRecorder started"
        );

        callbacks.onStart?.();
      };

      this.mediaRecorder.ondataavailable =
        (event: BlobEvent) => {

            if (event.data.size <= 0) {
            return;
            }

            this.audioChunks.push(
            event.data
            );

            /*
            * Send every MediaRecorder chunk
            * to the WebSocket.
            */
            callbacks.onChunk?.(
            event.data
            );
        };

      this.mediaRecorder.onerror = () => {
        callbacks.onError?.(
          new Error(
            "MediaRecorder encountered an error."
          )
        );
      };

      this.mediaRecorder.onstop = () => {
        const type =
          this.mediaRecorder?.mimeType ||
          mimeType ||
          "audio/webm";

        const audioBlob =
          new Blob(
            this.audioChunks,
            {
              type,
            }
          );

        console.log(
          "🎵 Recording complete"
        );

        console.log(
          "Type:",
          audioBlob.type
        );

        console.log(
          "Size:",
          audioBlob.size,
          "bytes"
        );

        /*
         * Only send the audio if this was
         * a real recording stop.
         *
         * destroy() should not upload audio.
         */
        if (
          this.stoppingManually &&
          audioBlob.size > 0
        ) {
          callbacks.onStop?.(
            audioBlob
          );
        }

        this.cleanup();
      };

      /*
       * Produce chunks every second.
       */
      this.mediaRecorder.start(1000);

    } catch (error) {
      console.error(
        "❌ Failed to start recording:",
        error
      );

      this.cleanup();

      callbacks.onError?.(
        error instanceof Error
          ? error
          : new Error(
              "Could not access microphone."
            )
      );

      throw error;
    }
  }

  stop(): void {
    if (
      !this.mediaRecorder ||
      this.mediaRecorder.state ===
        "inactive"
    ) {
      return;
    }

    console.log(
      "🛑 Stopping MediaRecorder..."
    );

    this.stoppingManually = true;

    this.mediaRecorder.stop();
  }

  isRecording(): boolean {
    return (
      this.mediaRecorder?.state ===
        "recording"
    );
  }

  private getSupportedMimeType():
    | string
    | null {
    const mimeTypes = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/ogg;codecs=opus",
      "audio/mp4",
    ];

    for (const mimeType of mimeTypes) {
      if (
        MediaRecorder.isTypeSupported(
          mimeType
        )
      ) {
        return mimeType;
      }
    }

    return null;
  }

  private cleanup(): void {
    if (this.stream) {
      this.stream
        .getTracks()
        .forEach((track) => {
          track.stop();
        });
    }

    this.stream = null;
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.stoppingManually = false;
  }

  destroy(): void {
    if (
      this.mediaRecorder &&
      this.mediaRecorder.state !==
        "inactive"
    ) {
      /*
       * This is NOT a real recording completion.
       * Don't upload it.
       */
      this.stoppingManually = false;

      this.mediaRecorder.stop();

      return;
    }

    this.cleanup();
  }
}