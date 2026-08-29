import { useEffect, useRef, useState } from "react";

type Props = {
  onTranscript: (text: string) => void;
  onRecordingStart?: () => void;
  onRecordingStop?: () => void;
  disabled?: boolean;
};

type SpeechRecognitionResultLike = {
  isFinal: boolean;
  [index: number]: {
    transcript: string;
  };
};

type SpeechRecognitionEventLike = Event & {
  results: {
    length: number;
    [index: number]: SpeechRecognitionResultLike;
  };
};

type SpeechRecognitionErrorEventLike = {
  error: string;
};

type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;

  start: () => void;
  stop: () => void;
  abort: () => void;

  onstart: (() => void) | null;
  onend: (() => void) | null;

  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;

  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

export default function VoiceRecorder({
  onTranscript,
  onRecordingStart,
  onRecordingStop,
  disabled = false,
}: Props) {
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);

  /*
   * Whether the user is intentionally recording.
   *
   * This is different from the browser's
   * SpeechRecognition running state because Chrome
   * can stop/restart recognition internally.
   */
  const shouldContinueRef = useRef(false);

  /*
   * Complete words/sentences that SpeechRecognition
   * has marked as final.
   */
  const finalTranscriptRef = useRef("");

  /*
   * Current temporary/interim words.
   */
  const interimTranscriptRef = useRef("");

  /*
   * Used to detect when no NEW words have arrived.
   */
  const lastTranscriptRef = useRef("");

  const silenceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const restartingRef = useRef(false);

  const [isRecording, setIsRecording] = useState(false);

  const [liveTranscript, setLiveTranscript] = useState("");

  const [error, setError] = useState<string | null>(null);

  /*
   * If the recognized transcript does not change
   * for this amount of time, the utterance is done.
   *
   * This is NOT based on microphone volume.
   *
   * It is based on new recognized words.
   */
  const WORD_PAUSE_TIMEOUT = 1500;

  function clearPauseTimer() {
    if (silenceTimerRef.current) {
      clearTimeout(silenceTimerRef.current);

      silenceTimerRef.current = null;
    }
  }

  function getCurrentTranscript() {
    const finalText = finalTranscriptRef.current.trim();

    const interimText = interimTranscriptRef.current.trim();

    return [finalText, interimText].filter(Boolean).join(" ").trim();
  }

  function finishRecording() {
    console.log("🛑 Finishing voice recording...");

    clearPauseTimer();

    shouldContinueRef.current = false;

    restartingRef.current = false;

    const recognition = recognitionRef.current;

    if (recognition) {
      try {
        recognition.stop();
      } catch {
        // Recognition may already be stopped.
      }
    }

    /*
     * Only use FINAL speech here.
     *
     * Interim speech can disappear/change.
     */
    const finalText = finalTranscriptRef.current.trim();

    if (finalText) {
      console.log("✅ Final transcript:", finalText);

      /*
       * THIS is where onTranscript is used.
       *
       * VoiceMode / ChatInput receives the
       * completed utterance here.
       */
      onTranscript(finalText);
    }

    finalTranscriptRef.current = "";
    interimTranscriptRef.current = "";
    lastTranscriptRef.current = "";

    setLiveTranscript("");
    setIsRecording(false);

    onRecordingStop?.();
  }

  function startRecording() {
    if (disabled) {
      return;
    }

    const SpeechRecognition =
      window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setError("Speech recognition is not supported in this browser.");

      return;
    }

    /*
     * Don't create multiple recognition instances.
     */
    if (shouldContinueRef.current) {
      return;
    }

    clearPauseTimer();

    setError(null);
    setLiveTranscript("");

    finalTranscriptRef.current = "";
    interimTranscriptRef.current = "";
    lastTranscriptRef.current = "";

    shouldContinueRef.current = true;

    const recognition = new SpeechRecognition();

    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = "en-IN";

    recognition.onstart = () => {
      console.log("🎙 Speech recognition started");

      restartingRef.current = false;

      setIsRecording(true);

      onRecordingStart?.();
    };

    recognition.onresult = (event: SpeechRecognitionEventLike) => {
      let finalText = "";
      let interimText = "";

      /*
       * Read the complete result set.
       */
      for (let i = 0; i < event.results.length; i++) {
        const result = event.results[i];

        const text = result[0].transcript;

        if (result.isFinal) {
          finalText += text + " ";
        } else {
          interimText += text + " ";
        }
      }

      finalText = finalText.trim();

      interimText = interimText.trim();

      /*
       * If the browser gives us final words,
       * append them to our permanent transcript.
       */
      if (finalText) {
        const previousFinal = finalTranscriptRef.current;

        /*
         * Avoid blindly duplicating the same
         * final transcript when Chrome sends
         * overlapping results.
         */
        if (!previousFinal.endsWith(finalText)) {
          finalTranscriptRef.current = [previousFinal, finalText]
            .filter(Boolean)
            .join(" ")
            .trim();
        }
      }

      interimTranscriptRef.current = interimText;

      const currentTranscript = getCurrentTranscript();

      /*
       * Show live text immediately.
       */
      if (currentTranscript) {
        console.log("📝 Live transcript:", currentTranscript);

        setLiveTranscript(currentTranscript);
      }

      /*
       * Detect NEW WORDS / NEW TRANSCRIPT.
       *
       * We don't look at microphone volume.
       */
      const transcriptChanged = currentTranscript !== lastTranscriptRef.current;

      if (transcriptChanged) {
        lastTranscriptRef.current = currentTranscript;

        /*
         * New words arrived.
         *
         * Reset the completion timer.
         */
        clearPauseTimer();

        silenceTimerRef.current = setTimeout(() => {
          console.log("⏱ No new words detected.");

          console.log("🛑 Completing utterance...");

          finishRecording();
        }, WORD_PAUSE_TIMEOUT);
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEventLike) => {
      console.error("❌ Speech recognition error:", event.error);

      /*
       * Chrome can produce no-speech when
       * nothing was recognized yet.
       *
       * Don't destroy the entire UI for it.
       */
      if (event.error === "no-speech") {
        return;
      }

      if (event.error === "aborted") {
        return;
      }

      clearPauseTimer();

      shouldContinueRef.current = false;

      setIsRecording(false);

      setError(`Speech recognition error: ${event.error}`);

      onRecordingStop?.();
    };

    recognition.onend = () => {
      console.log("🎙 Speech recognition ended");

      /*
       * Chrome sometimes ends recognition
       * even though continuous=true.
       *
       * If the user hasn't finished speaking,
       * restart it.
       */
      if (shouldContinueRef.current) {
        if (restartingRef.current) {
          return;
        }

        restartingRef.current = true;

        console.log("🔄 Restarting speech recognition...");

        setTimeout(() => {
          if (!shouldContinueRef.current) {
            restartingRef.current = false;

            return;
          }

          try {
            recognition.start();
          } catch (error) {
            console.warn("Could not restart recognition:", error);
          }
        }, 100);

        return;
      }

      setIsRecording(false);
    };

    recognitionRef.current = recognition;

    try {
      recognition.start();
    } catch (error) {
      console.error("❌ Could not start speech recognition:", error);

      shouldContinueRef.current = false;

      setIsRecording(false);

      setError("Could not start speech recognition.");
    }
  }

  function handleClick() {
    if (disabled) {
      return;
    }

    if (isRecording) {
      finishRecording();
    } else {
      startRecording();
    }
  }

  useEffect(() => {
    return () => {
      clearPauseTimer();

      shouldContinueRef.current = false;

      restartingRef.current = false;

      recognitionRef.current?.abort();

      recognitionRef.current = null;
    };
  }, []);

  return (
    <div className="relative">
      {/* Microphone */}
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled}
        title={isRecording ? "Stop dictation" : "Start dictation"}
        className={`
          w-10
          h-10
          shrink-0
          rounded-xl
          transition
          flex
          items-center
          justify-center

          ${
            isRecording
              ? "bg-red-600 hover:bg-red-700 animate-pulse"
              : "hover:bg-[#2a2f3a]"
          }

          ${disabled ? "opacity-50 cursor-not-allowed" : ""}
        `}
      >
        {isRecording ? "■" : "🎙"}
      </button>

      {/* Live transcript */}
      {isRecording && (
        <div
          className="
            absolute
            bottom-14
            left-0
            z-50
            w-80
            max-w-[80vw]

            rounded-xl
            border
            border-[#30363d]

            bg-[#161b22]
            shadow-2xl

            px-4
            py-3

            text-sm
            text-gray-200

            backdrop-blur-xl
          "
        >
          <div
            className="
              text-xs
              text-gray-500
              mb-1
            "
          >
            Listening...
          </div>

          <div>{liveTranscript || "Speak now..."}</div>

          <div
            className="
              mt-2
              text-[11px]
              text-gray-600
            "
          >
            Stops after 1.5s without new words
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div
          className="
            absolute
            bottom-14
            left-0
            z-50

            w-64

            rounded-lg
            border
            border-red-500/30

            bg-[#161b22]

            px-3
            py-2

            text-xs
            text-red-400
          "
        >
          {error}
        </div>
      )}
    </div>
  );
}
