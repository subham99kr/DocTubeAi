import { useCallback, useEffect, useRef, useState } from "react";
import { useChat } from "../../context/ChatContext";

type Props = {
  onClose: () => void;
  onTranscript: (text: string) => void;
};

type VoiceEvent =
  | { type: "connected" }
  | { type: "session_started" }
  | { type: "user_speech_started"; turn_id: number }
  | { type: "transcript_partial"; text: string; turn_id: number }
  | { type: "transcript_final"; text: string; turn_id: number }
  | { type: "user_turn_complete"; text: string; turn_id: number }
  | { type: "assistant_started"; turn_id: number }
  | { type: "assistant_status"; message: string; turn_id: number }
  | { type: "assistant_text"; text: string; turn_id: number }
  | {
      type: "assistant_audio";
      data: string;
      turn_id: number;
      mime_type?: string;
    }
  | { type: "assistant_completed"; turn_id: number }
  | { type: "interrupted"; turn_id: number }
  | { type: "pong" }
  | { type: "error"; message?: string; code?: string; data?: string }
  | { type: "session_ended" };

type AudioChunk = {
  turnId: number;
  chunkId: number;
  bytes: ArrayBuffer;
  mimeType: string;
};

const DEFAULT_AUDIO_MIME = "audio/mpeg";

export default function VoiceMode({
  onClose,
  onTranscript,
}: Props) {
  const { sessionId } = useChat();

  const mountedRef = useRef(false);
  const lifecycleIdRef = useRef(0);

  const websocketRef = useRef<WebSocket | null>(null);
  const connectingRef = useRef(false);
  const sessionStartedRef = useRef(false);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const microphoneStartedRef = useRef(false);

  const activeUserTurnIdRef = useRef<number | null>(null);
  const activeAssistantTurnIdRef = useRef<number | null>(null);

  const latestUserTurnIdRef = useRef(-1);
  const latestAssistantTurnIdRef = useRef(-1);

  const assistantGeneratingRef = useRef(false);
  const assistantSpeakingRef = useRef(false);

  /*
   * ============================================================
   * CONTINUOUS AUDIO STREAM
   * ============================================================
   *
   * Backend sends:
   *
   *   audio chunk 1
   *   audio chunk 2
   *   audio chunk 3
   *   ...
   *
   * These are NOT separate audio files.
   *
   * They are consecutive MP3 bytes belonging to ONE stream.
   *
   * Therefore:
   *
   *   DO NOT create one Audio() per chunk.
   *   DO NOT create one Blob per chunk.
   *
   * We use ONE MediaSource + ONE HTMLAudioElement.
   */

  const audioChunkQueueRef = useRef<AudioChunk[]>([]);
  const audioAppendingRef = useRef(false);

  const mediaSourceRef = useRef<MediaSource | null>(null);
  const sourceBufferRef = useRef<SourceBuffer | null>(null);

  const streamAudioRef = useRef<HTMLAudioElement | null>(null);

  const mediaSourceObjectUrlRef = useRef<string | null>(null);

  const audioStreamTurnIdRef = useRef<number | null>(null);
  const audioStreamStartedRef = useRef(false);
  const audioStreamCompletedRef = useRef(false);
  const audioSourceOpenedRef = useRef(false);

  const nextAudioChunkIdRef = useRef(0);

  const [isConnected, setIsConnected] = useState(false);
  const [isMicrophoneReady, setIsMicrophoneReady] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [isAssistantSpeaking, setIsAssistantSpeaking] =
    useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  const [liveTranscript, setLiveTranscript] = useState("");
  const [transcript, setTranscript] = useState("");

  const [assistantResponse, setAssistantResponse] =
    useState("");
  const [assistantStatus, setAssistantStatus] =
    useState("");

  const [error, setError] = useState<string | null>(null);

  const safeSet = useCallback(
    (fn: () => void, lifecycleId?: number) => {
      if (!mountedRef.current) {
        return;
      }

      if (
        lifecycleId !== undefined &&
        lifecycleId !== lifecycleIdRef.current
      ) {
        return;
      }

      fn();
    },
    [],
  );

  const getSessionId = useCallback(() => {
    const id =
      typeof sessionId === "string"
        ? sessionId.trim()
        : "";

    if (!id) {
      throw new Error(
        "Voice session ID is missing from ChatContext.",
      );
    }

    return id;
  }, [sessionId]);

  const getWebSocketUrl = useCallback(() => {
    const base = (
      import.meta.env.VITE_BACKEND_URL ||
      "http://127.0.0.1:8000"
    )
      .trim()
      .replace(/\/+$/, "");

    if (!base) {
      throw new Error(
        "VITE_BACKEND_URL is not configured.",
      );
    }

    const wsBase = base
      .replace(/^https:\/\//i, "wss://")
      .replace(/^http:\/\//i, "ws://");

    return `${wsBase}/voice/ws/${encodeURIComponent(
      getSessionId(),
    )}`;
  }, [getSessionId]);

  /*
   * ============================================================
   * BASE64 -> ARRAYBUFFER
   * ============================================================
   */

  const decodeBase64Audio = useCallback(
    (value: string): ArrayBuffer => {
      if (!value) {
        throw new Error(
          "Assistant audio data is empty.",
        );
      }

      const binary = atob(value);

      const buffer = new ArrayBuffer(
        binary.length,
      );

      const bytes = new Uint8Array(buffer);

      for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i);
      }

      return buffer;
    },
    [],
  );

  /*
   * ============================================================
   * MICROPHONE
   * ============================================================
   */

  const pauseMicrophone = useCallback(() => {
    const recorder = mediaRecorderRef.current;

    if (recorder?.state === "recording") {
      try {
        recorder.pause();

        console.info("[Voice][Mic] paused");
      } catch (err) {
        console.warn(
          "[Voice][Mic] pause failed",
          err,
        );
      }
    }

    safeSet(() => {
      setIsListening(false);
    });
  }, [safeSet]);

  const resumeMicrophone = useCallback(() => {
    if (!mountedRef.current) {
      return;
    }

    if (assistantGeneratingRef.current) {
      return;
    }

    if (assistantSpeakingRef.current) {
      return;
    }

    const recorder = mediaRecorderRef.current;

    if (recorder?.state === "paused") {
      try {
        recorder.resume();

        console.info("[Voice][Mic] resumed");

        safeSet(() => {
          setIsListening(true);
        });
      } catch (err) {
        console.warn(
          "[Voice][Mic] resume failed",
          err,
        );
      }
    }
  }, [safeSet]);

  /*
   * ============================================================
   * CLEAN CONTINUOUS AUDIO STREAM
   * ============================================================
   */

  const cleanupAudioStream = useCallback(() => {
    console.info(
      "[Voice][Audio] Cleaning continuous stream",
    );

    audioChunkQueueRef.current = [];

    audioAppendingRef.current = false;

    audioStreamStartedRef.current = false;
    audioStreamCompletedRef.current = false;
    audioSourceOpenedRef.current = false;

    audioStreamTurnIdRef.current = null;

    nextAudioChunkIdRef.current = 0;

    const audio = streamAudioRef.current;

    if (audio) {
      try {
        audio.pause();

        audio.onended = null;
        audio.onerror = null;
        audio.onabort = null;

        audio.removeAttribute("src");
        audio.load();
      } catch {
        // cleanup
      }
    }

    streamAudioRef.current = null;

    const sourceBuffer =
      sourceBufferRef.current;

    if (sourceBuffer) {
      sourceBuffer.onupdateend = null;
      sourceBuffer.onerror = null;
    }

    sourceBufferRef.current = null;

    const mediaSource =
      mediaSourceRef.current;

    if (mediaSource) {
      mediaSource.onsourceopen = null;
      mediaSource.onsourceended = null;
      mediaSource.onsourceclose = null;
    }

    mediaSourceRef.current = null;

    const objectUrl =
      mediaSourceObjectUrlRef.current;

    if (objectUrl) {
      try {
        URL.revokeObjectURL(objectUrl);
      } catch {
        // cleanup
      }
    }

    mediaSourceObjectUrlRef.current = null;
  }, []);

  /*
   * ============================================================
   * FINISH AUDIO STREAM
   * ============================================================
   */

  const finishAudioStream = useCallback(() => {
    const mediaSource =
      mediaSourceRef.current;

    const sourceBuffer =
      sourceBufferRef.current;

    if (!mediaSource || !sourceBuffer) {
      return;
    }

    if (!audioStreamCompletedRef.current) {
      return;
    }

    if (audioChunkQueueRef.current.length > 0) {
      return;
    }

    if (sourceBuffer.updating) {
      return;
    }

    if (
      mediaSource.readyState === "open"
    ) {
      try {
        console.info(
          "[Voice][Audio] Ending continuous stream",
        );

        mediaSource.endOfStream();
      } catch (err) {
        console.warn(
          "[Voice][Audio] endOfStream failed",
          err,
        );
      }
    }
  }, []);

  /*
   * ============================================================
   * APPEND NEXT MP3 CHUNK
   * ============================================================
   */

  const appendNextAudioChunk = useCallback(() => {
    const sourceBuffer =
      sourceBufferRef.current;

    if (!sourceBuffer) {
      return;
    }

    if (audioAppendingRef.current) {
      return;
    }

    if (sourceBuffer.updating) {
      return;
    }

    const chunk =
      audioChunkQueueRef.current.shift();

    if (!chunk) {
      finishAudioStream();

      return;
    }

    if (
      audioStreamTurnIdRef.current !==
      chunk.turnId
    ) {
      console.warn(
        "[Voice][Audio] Dropping stale stream chunk",
        {
          chunkTurnId: chunk.turnId,
          activeTurnId:
            audioStreamTurnIdRef.current,
          chunkId: chunk.chunkId,
        },
      );

      appendNextAudioChunk();

      return;
    }

    audioAppendingRef.current = true;

    try {
      /*
       * IMPORTANT:
       *
       * appendBuffer() receives the RAW MP3 bytes.
       *
       * We do NOT wrap this chunk inside a Blob.
       * We do NOT create another Audio().
       *
       * Every chunk is appended to the SAME SourceBuffer.
       */

      sourceBuffer.appendBuffer(
        chunk.bytes,
      );

      console.info(
        "[Voice][Audio] APPEND stream chunk",
        {
          turnId: chunk.turnId,
          chunkId: chunk.chunkId,
          bytes: chunk.bytes.byteLength,
          queueRemaining:
            audioChunkQueueRef.current.length,
        },
      );
    } catch (err) {
      audioAppendingRef.current = false;

      console.error(
        "[Voice][Audio] appendBuffer failed",
        {
          turnId: chunk.turnId,
          chunkId: chunk.chunkId,
          error: err,
        },
      );

      safeSet(() => {
        setError(
          err instanceof Error
            ? err.message
            : "Could not append assistant audio.",
        );
      });

      /*
       * Do not kill the whole voice session because one
       * append failed.
       *
       * Continue with the next chunk.
       */
      appendNextAudioChunk();
    }
  }, [finishAudioStream, safeSet]);

  /*
   * ============================================================
   * START CONTINUOUS AUDIO STREAM
   * ============================================================
   */

  const startAudioStream = useCallback(
    (turnId: number, mimeType: string) => {
      /*
       * If the current stream belongs to this turn then
       * nothing needs to be recreated.
       */

      if (
        audioStreamStartedRef.current &&
        audioStreamTurnIdRef.current ===
          turnId
      ) {
        return;
      }

      /*
       * A new assistant turn always gets a completely
       * new MediaSource.
       */

      cleanupAudioStream();

      audioStreamTurnIdRef.current =
        turnId;

      audioStreamStartedRef.current = true;

      audioStreamCompletedRef.current =
        false;

      const normalizedMime =
        mimeType || DEFAULT_AUDIO_MIME;

      if (
        !MediaSource.isTypeSupported(
          normalizedMime,
        )
      ) {
        console.error(
          "[Voice][Audio] MediaSource does not support",
          normalizedMime,
        );

        safeSet(() => {
          setError(
            `Browser does not support ${normalizedMime} streaming.`,
          );
        });

        return;
      }

      const mediaSource = new MediaSource();

      mediaSourceRef.current =
        mediaSource;

      const objectUrl =
        URL.createObjectURL(mediaSource);

      mediaSourceObjectUrlRef.current =
        objectUrl;

      const audio = new Audio();

      audio.preload = "auto";

      audio.src = objectUrl;

      streamAudioRef.current = audio;

      audio.onended = () => {
        console.info(
          "[Voice][Audio] COMPLETE stream playback",
          {
            turnId,
          },
        );

        assistantSpeakingRef.current =
          false;

        safeSet(() => {
          setIsAssistantSpeaking(false);
        });

        resumeMicrophone();
      };

      audio.onerror = (event) => {
        console.error(
          "[Voice][Audio] continuous stream error",
          {
            turnId,
            event,
            mediaError: audio.error,
          },
        );

        assistantSpeakingRef.current =
          false;

        safeSet(() => {
          setIsAssistantSpeaking(false);

          setError(
            "Browser could not play assistant audio stream.",
          );
        });

        resumeMicrophone();
      };

      mediaSource.onsourceopen = () => {
        if (
          mediaSourceRef.current !==
          mediaSource
        ) {
          return;
        }

        console.info(
          "[Voice][Audio] START continuous stream",
          {
            turnId,
            mimeType: normalizedMime,
          },
        );

        audioSourceOpenedRef.current =
          true;

        try {
          const sourceBuffer =
            mediaSource.addSourceBuffer(
              normalizedMime,
            );

          sourceBuffer.mode =
            "sequence";

          sourceBufferRef.current =
            sourceBuffer;

          sourceBuffer.onupdateend = () => {
            audioAppendingRef.current =
              false;

            /*
             * First chunk has now been appended.
             * Start the ONE audio element.
             */

            if (
              !assistantSpeakingRef.current
            ) {
              assistantSpeakingRef.current =
                true;

              safeSet(() => {
                setIsAssistantSpeaking(true);
              });
            }

            const currentAudio =
              streamAudioRef.current;

            if (
              currentAudio &&
              currentAudio.paused
            ) {
              void currentAudio
                .play()
                .then(() => {
                  console.info(
                    "[Voice][Audio] PLAYING continuous stream",
                    {
                      turnId,
                    },
                  );
                })
                .catch((err) => {
                  console.error(
                    "[Voice][Audio] play failed",
                    err,
                  );

                  safeSet(() => {
                    setError(
                      err instanceof Error
                        ? err.message
                        : "Assistant audio playback failed.",
                    );
                  });
                });
            }

            /*
             * Append exactly ONE next chunk.
             *
             * This is critical.
             *
             * We NEVER call appendBuffer while
             * SourceBuffer.updating === true.
             */

            appendNextAudioChunk();
          };

          sourceBuffer.onerror = (event) => {
            audioAppendingRef.current =
              false;

            console.error(
              "[Voice][Audio] SourceBuffer error",
              {
                turnId,
                event,
              },
            );

            safeSet(() => {
              setError(
                "Assistant audio stream failed.",
              );
            });
          };

          /*
           * There may already be chunks waiting
           * before sourceopen happened.
           */

          appendNextAudioChunk();
        } catch (err) {
          console.error(
            "[Voice][Audio] Could not create SourceBuffer",
            err,
          );

          safeSet(() => {
            setError(
              err instanceof Error
                ? err.message
                : "Could not initialize audio stream.",
            );
          });
        }
      };

      mediaSource.onsourceended = () => {
        console.info(
          "[Voice][Audio] MediaSource ended",
          {
            turnId,
          },
        );
      };

      mediaSource.onsourceclose = () => {
        console.info(
          "[Voice][Audio] MediaSource closed",
          {
            turnId,
          },
        );
      };
    },
    [
      appendNextAudioChunk,
      cleanupAudioStream,
      resumeMicrophone,
      safeSet,
    ],
  );

  /*
   * ============================================================
   * QUEUE CONTINUOUS AUDIO CHUNK
   * ============================================================
   */

  const enqueueAssistantAudio =
    useCallback(
      (
        event: Extract<
          VoiceEvent,
          { type: "assistant_audio" }
        >,
      ) => {
        if (
          activeAssistantTurnIdRef.current !==
          event.turn_id
        ) {
          console.warn(
            "[Voice][Audio] Ignoring stale audio",
            {
              eventTurn: event.turn_id,
              activeTurn:
                activeAssistantTurnIdRef.current,
            },
          );

          return;
        }

        try {
          const bytes =
            decodeBase64Audio(event.data);

          const mimeType =
            event.mime_type?.trim() ||
            DEFAULT_AUDIO_MIME;

          /*
           * Start ONE continuous stream for
           * this assistant turn.
           */

          if (
            !audioStreamStartedRef.current ||
            audioStreamTurnIdRef.current !==
              event.turn_id
          ) {
            startAudioStream(
              event.turn_id,
              mimeType,
            );
          }

          const chunk: AudioChunk = {
            turnId: event.turn_id,
            chunkId:
              nextAudioChunkIdRef.current++,
            bytes,
            mimeType,
          };

          audioChunkQueueRef.current.push(
            chunk,
          );

          console.info(
            "[Voice][Audio] QUEUED stream chunk",
            {
              turnId: chunk.turnId,
              chunkId: chunk.chunkId,
              bytes: chunk.bytes.byteLength,
              queueLength:
                audioChunkQueueRef.current
                  .length,
              appending:
                audioAppendingRef.current,
            },
          );

          /*
           * If SourceBuffer is already available,
           * immediately feed it.
           *
           * Otherwise sourceopen will do it.
           */

          if (
            audioSourceOpenedRef.current
          ) {
            appendNextAudioChunk();
          }
        } catch (err) {
          console.error(
            "[Voice][Audio] decode failed",
            err,
          );

          safeSet(() => {
            setError(
              err instanceof Error
                ? err.message
                : "Could not decode assistant audio.",
            );
          });
        }
      },
      [
        appendNextAudioChunk,
        decodeBase64Audio,
        safeSet,
        startAudioStream,
      ],
    );

  /*
   * ============================================================
   * STOP ASSISTANT AUDIO
   * ============================================================
   */

  const stopAssistantPlayback =
    useCallback(
      (resumeAfter: boolean) => {
        console.info(
          "[Voice][Audio] INTERRUPT / CLEAR",
          {
            queued:
              audioChunkQueueRef.current
                .length,
          },
        );

        cleanupAudioStream();

        assistantSpeakingRef.current =
          false;

        assistantGeneratingRef.current =
          false;

        safeSet(() => {
          setIsAssistantSpeaking(false);
        });

        if (resumeAfter) {
          resumeMicrophone();
        }
      },
      [
        cleanupAudioStream,
        resumeMicrophone,
        safeSet,
      ],
    );

  /*
   * ============================================================
   * MICROPHONE START
   * ============================================================
   */

  const startMicrophone = useCallback(
    async (lifecycleId: number) => {
      if (
        microphoneStartedRef.current ||
        !mountedRef.current ||
        lifecycleId !==
          lifecycleIdRef.current
      ) {
        return;
      }

      const ws = websocketRef.current;

      if (
        !ws ||
        ws.readyState !== WebSocket.OPEN
      ) {
        console.warn(
          "[Voice][Mic] WebSocket is not open",
        );

        return;
      }

      try {
        const stream =
          await navigator.mediaDevices.getUserMedia(
            {
              audio: {
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
              },
            },
          );

        if (
          !mountedRef.current ||
          lifecycleId !==
            lifecycleIdRef.current
        ) {
          stream
            .getTracks()
            .forEach((track) =>
              track.stop(),
            );

          return;
        }

        mediaStreamRef.current =
          stream;

        let mimeType = "";

        if (
          MediaRecorder.isTypeSupported(
            "audio/webm;codecs=opus",
          )
        ) {
          mimeType =
            "audio/webm;codecs=opus";
        } else if (
          MediaRecorder.isTypeSupported(
            "audio/webm",
          )
        ) {
          mimeType = "audio/webm";
        } else if (
          MediaRecorder.isTypeSupported(
            "audio/ogg;codecs=opus",
          )
        ) {
          mimeType =
            "audio/ogg;codecs=opus";
        }

        const recorder = mimeType
          ? new MediaRecorder(stream, {
              mimeType,
            })
          : new MediaRecorder(stream);

        mediaRecorderRef.current =
          recorder;

        microphoneStartedRef.current =
          true;

        recorder.ondataavailable = (
          event,
        ) => {
          if (
            !mountedRef.current ||
            lifecycleId !==
              lifecycleIdRef.current
          ) {
            return;
          }

          if (!event.data?.size) {
            return;
          }

          /*
           * NEVER send microphone audio while
           * assistant is generating or speaking.
           */

          if (
            assistantGeneratingRef.current ||
            assistantSpeakingRef.current
          ) {
            return;
          }

          const socket =
            websocketRef.current;

          if (
            !socket ||
            socket.readyState !==
              WebSocket.OPEN
          ) {
            return;
          }

          try {
            socket.send(event.data);
          } catch (err) {
            console.error(
              "[Voice][Mic] send failed",
              err,
            );
          }
        };

        recorder.onstart = () => {
          console.info(
            "[Voice][Mic] recording started",
            {
              mimeType:
                recorder.mimeType,
            },
          );

          safeSet(
            () => {
              setIsListening(true);
              setIsMicrophoneReady(true);
            },
            lifecycleId,
          );
        };

        recorder.onstop = () => {
          safeSet(
            () =>
              setIsListening(false),
            lifecycleId,
          );
        };

        recorder.onerror = (event) => {
          console.error(
            "[Voice][Mic] recorder error",
            event,
          );

          safeSet(
            () => {
              setError(
                "Microphone recording failed.",
              );

              setIsListening(false);
            },
            lifecycleId,
          );
        };

        recorder.start(250);
      } catch (err) {
        microphoneStartedRef.current =
          false;

        console.error(
          "[Voice][Mic] start failed",
          err,
        );

        safeSet(
          () => {
            setIsMicrophoneReady(false);
            setIsListening(false);

            setError(
              err instanceof Error
                ? err.message
                : "Could not access microphone.",
            );
          },
          lifecycleId,
        );
      }
    },
    [safeSet],
  );

  /*
   * ============================================================
   * CLEANUP
   * ============================================================
   */

  const cleanup = useCallback(() => {
    console.info("[Voice] cleanup");

    lifecycleIdRef.current += 1;

    connectingRef.current = false;
    sessionStartedRef.current = false;
    microphoneStartedRef.current = false;

    assistantGeneratingRef.current =
      false;

    assistantSpeakingRef.current =
      false;

    activeUserTurnIdRef.current = null;
    activeAssistantTurnIdRef.current =
      null;

    latestUserTurnIdRef.current = -1;
    latestAssistantTurnIdRef.current = -1;

    cleanupAudioStream();

    const recorder =
      mediaRecorderRef.current;

    mediaRecorderRef.current = null;

    if (
      recorder &&
      recorder.state !== "inactive"
    ) {
      try {
        recorder.ondataavailable = null;
        recorder.onstart = null;
        recorder.onstop = null;
        recorder.onerror = null;

        recorder.stop();
      } catch {
        // cleanup
      }
    }

    const stream =
      mediaStreamRef.current;

    mediaStreamRef.current = null;

    stream
      ?.getTracks()
      .forEach((track) => {
        try {
          track.stop();
        } catch {
          // cleanup
        }
      });

    const ws =
      websocketRef.current;

    websocketRef.current = null;

    if (ws) {
      ws.onopen = null;
      ws.onmessage = null;
      ws.onerror = null;
      ws.onclose = null;

      try {
        if (
          ws.readyState ===
            WebSocket.OPEN ||
          ws.readyState ===
            WebSocket.CONNECTING
        ) {
          ws.close();
        }
      } catch {
        // cleanup
      }
    }

    if (mountedRef.current) {
      setIsConnected(false);
      setIsMicrophoneReady(false);
      setIsListening(false);
      setIsAssistantSpeaking(false);
      setIsProcessing(false);
    }
  }, [cleanupAudioStream]);

  /*
   * ============================================================
   * WEBSOCKET EVENTS
   * ============================================================
   */

  const handleWebSocketEvent =
    useCallback(
      (
        event: VoiceEvent,
        lifecycleId: number,
      ) => {
        if (
          !mountedRef.current ||
          lifecycleId !==
            lifecycleIdRef.current
        ) {
          return;
        }

        console.info(
          "[Voice] Handling event:",
          event,
        );

        switch (event.type) {
          case "connected": {
            safeSet(
              () => {
                setIsConnected(true);
                setError(null);
              },
              lifecycleId,
            );

            return;
          }

          case "session_started": {
            sessionStartedRef.current =
              true;

            void startMicrophone(
              lifecycleId,
            );

            return;
          }

          case "user_speech_started": {
            if (
              event.turn_id <
              latestUserTurnIdRef.current
            ) {
              return;
            }

            latestUserTurnIdRef.current =
              event.turn_id;

            activeUserTurnIdRef.current =
              event.turn_id;

            /*
             * User interrupted assistant.
             */

            if (
              assistantGeneratingRef.current ||
              assistantSpeakingRef.current
            ) {
              stopAssistantPlayback(
                false,
              );

              activeAssistantTurnIdRef.current =
                null;
            }

            safeSet(
              () => {
                setIsListening(true);
                setIsProcessing(false);
                setLiveTranscript("");
              },
              lifecycleId,
            );

            return;
          }

          case "transcript_partial": {
            if (
              event.turn_id <
              latestUserTurnIdRef.current
            ) {
              return;
            }

            latestUserTurnIdRef.current =
              event.turn_id;

            activeUserTurnIdRef.current =
              event.turn_id;

            safeSet(
              () =>
                setLiveTranscript(
                  event.text,
                ),
              lifecycleId,
            );

            return;
          }

          case "transcript_final": {
            if (
              event.turn_id <
              latestUserTurnIdRef.current
            ) {
              return;
            }

            latestUserTurnIdRef.current =
              event.turn_id;

            safeSet(
              () => {
                setTranscript(
                  event.text,
                );

                setLiveTranscript(
                  event.text,
                );
              },
              lifecycleId,
            );

            return;
          }

          case "user_turn_complete": {
            if (
              event.turn_id <
              latestUserTurnIdRef.current
            ) {
              return;
            }

            latestUserTurnIdRef.current =
              event.turn_id;

            activeUserTurnIdRef.current =
              event.turn_id;

            safeSet(
              () => {
                setTranscript(
                  event.text,
                );

                setLiveTranscript(
                  event.text,
                );

                setIsListening(false);
                setIsProcessing(true);
              },
              lifecycleId,
            );

            return;
          }

          case "assistant_started": {
            if (
              event.turn_id <
              latestAssistantTurnIdRef.current
            ) {
              return;
            }

            latestAssistantTurnIdRef.current =
              event.turn_id;

            /*
             * New assistant turn.
             *
             * Kill ONLY the previous stream.
             */

            stopAssistantPlayback(
              false,
            );

            activeAssistantTurnIdRef.current =
              event.turn_id;

            assistantGeneratingRef.current =
              true;

            assistantSpeakingRef.current =
              false;

            pauseMicrophone();

            safeSet(
              () => {
                setAssistantResponse(
                  "",
                );

                setAssistantStatus(
                  "",
                );

                setIsProcessing(false);

                setIsAssistantSpeaking(
                  false,
                );
              },
              lifecycleId,
            );

            return;
          }

          case "assistant_status": {
            if (
              event.turn_id !==
              activeAssistantTurnIdRef.current
            ) {
              return;
            }

            safeSet(
              () => {
                setAssistantStatus(
                  event.message,
                );

                setIsProcessing(true);
              },
              lifecycleId,
            );

            return;
          }

          case "assistant_text": {
            if (
              event.turn_id !==
              activeAssistantTurnIdRef.current
            ) {
              return;
            }

            /*
             * TEXT IS COMPLETELY INDEPENDENT
             * FROM AUDIO.
             *
             * It is rendered immediately.
             *
             * At the same time the MP3 stream
             * is being appended to MediaSource.
             */

            safeSet(
              () =>
                setAssistantResponse(
                  (previous) =>
                    previous + event.text,
                ),
              lifecycleId,
            );

            return;
          }

          case "assistant_audio": {
            /*
             * ONLY enqueue raw MP3 bytes.
             *
             * No Audio().
             * No Blob URL per chunk.
             * No waiting for previous chunk.
             */

            enqueueAssistantAudio(
              event,
            );

            return;
          }

          case "assistant_completed": {
            if (
              event.turn_id !==
              activeAssistantTurnIdRef.current
            ) {
              return;
            }

            /*
             * IMPORTANT:
             *
             * This means backend generation is
             * finished.
             *
             * It does NOT mean playback is finished.
             */

            assistantGeneratingRef.current =
              false;

            audioStreamCompletedRef.current =
              true;

            safeSet(
              () => {
                setIsProcessing(false);
                setAssistantStatus("");
              },
              lifecycleId,
            );

            console.info(
              "[Voice] Assistant generation completed",
              {
                turnId:
                  event.turn_id,

                queuedAudio:
                  audioChunkQueueRef.current
                    .length,

                appending:
                  audioAppendingRef.current,
              },
            );

            /*
             * If all chunks have already been
             * appended, close MediaSource.
             *
             * Otherwise appendNextAudioChunk()
             * will eventually call finishAudioStream().
             */

            finishAudioStream();

            return;
          }

          case "interrupted": {
            stopAssistantPlayback(
              false,
            );

            activeAssistantTurnIdRef.current =
              null;

            safeSet(
              () => {
                setAssistantResponse(
                  "",
                );

                setAssistantStatus(
                  "",
                );

                setIsProcessing(false);

                setIsAssistantSpeaking(
                  false,
                );

                setIsListening(true);
              },
              lifecycleId,
            );

            resumeMicrophone();

            return;
          }

          case "pong": {
            console.info(
              "[Voice] pong",
            );

            return;
          }

          case "error": {
            const message =
              event.message ||
              event.data ||
              "Voice backend error.";

            console.error(
              "[Voice] backend error",
              {
                message,
                code: event.code,
              },
            );

            safeSet(
              () => {
                setError(message);
                setIsProcessing(false);
              },
              lifecycleId,
            );

            return;
          }

          case "session_ended": {
            cleanup();

            return;
          }

          default: {
            const exhaustive: never =
              event;

            console.warn(
              "[Voice] Unknown event:",
              exhaustive,
            );
          }
        }
      },
      [
        cleanup,
        enqueueAssistantAudio,
        finishAudioStream,
        pauseMicrophone,
        resumeMicrophone,
        safeSet,
        startMicrophone,
        stopAssistantPlayback,
      ],
    );

  /*
   * ============================================================
   * CONNECT WEBSOCKET
   * ============================================================
   */

  const connectWebSocket =
    useCallback(async () => {
      if (
        !mountedRef.current ||
        connectingRef.current
      ) {
        return;
      }

      const lifecycleId =
        lifecycleIdRef.current;

      let id: string;
      let url: string;

      try {
        id = getSessionId();
        url = getWebSocketUrl();
      } catch (err) {
        safeSet(
          () =>
            setError(
              err instanceof Error
                ? err.message
                : "Could not initialize voice mode.",
            ),
          lifecycleId,
        );

        return;
      }

      const existing =
        websocketRef.current;

      if (
        existing &&
        (existing.readyState ===
          WebSocket.OPEN ||
          existing.readyState ===
            WebSocket.CONNECTING)
      ) {
        return;
      }

      connectingRef.current = true;

      console.info(
        "[Voice] Connecting",
        {
          sessionId: id,
          url,
        },
      );

      await new Promise<void>(
        (resolve) => {
          let settled = false;

          const resolveOnce = () => {
            if (!settled) {
              settled = true;
              resolve();
            }
          };

          let ws: WebSocket;

          try {
            ws = new WebSocket(url);
          } catch (err) {
            connectingRef.current =
              false;

            safeSet(
              () =>
                setError(
                  err instanceof Error
                    ? err.message
                    : "Failed to create voice WebSocket.",
                ),
              lifecycleId,
            );

            resolveOnce();

            return;
          }

          websocketRef.current = ws;

          ws.onopen = () => {
            if (
              !mountedRef.current ||
              lifecycleId !==
                lifecycleIdRef.current
            ) {
              try {
                ws.close();
              } catch {
                // cleanup
              }

              resolveOnce();

              return;
            }

            connectingRef.current =
              false;

            safeSet(
              () => {
                setIsConnected(true);
                setError(null);
              },
              lifecycleId,
            );

            const message =
              JSON.stringify({
                type: "start_session",
              });

            console.info(
              "[Voice] ->",
              message,
            );

            ws.send(message);

            resolveOnce();
          };

          ws.onmessage = (
            message: MessageEvent,
          ) => {
            if (
              !mountedRef.current ||
              lifecycleId !==
                lifecycleIdRef.current
            ) {
              return;
            }

            if (
              typeof message.data !==
              "string"
            ) {
              console.warn(
                "[Voice] Unexpected binary WebSocket message",
              );

              return;
            }

            try {
              const parsed =
                JSON.parse(
                  message.data,
                ) as VoiceEvent;

              handleWebSocketEvent(
                parsed,
                lifecycleId,
              );
            } catch (err) {
              console.error(
                "[Voice] Invalid WebSocket JSON",
                {
                  err,
                  data: message.data,
                },
              );
            }
          };

          ws.onerror = (event) => {
            console.error(
              "[Voice] WebSocket error",
              event,
            );

            connectingRef.current =
              false;

            if (
              websocketRef.current ===
              ws
            ) {
              safeSet(
                () => {
                  setIsConnected(
                    false,
                  );

                  setError(
                    "Voice WebSocket connection failed.",
                  );
                },
                lifecycleId,
              );
            }

            resolveOnce();
          };

          ws.onclose = (event) => {
            connectingRef.current =
              false;

            console.info(
              "[Voice] WebSocket closed",
              {
                code: event.code,
                reason: event.reason,
                sessionId: id,
              },
            );

            if (
              websocketRef.current ===
              ws
            ) {
              websocketRef.current =
                null;

              sessionStartedRef.current =
                false;

              if (
                mountedRef.current &&
                lifecycleId ===
                  lifecycleIdRef.current
              ) {
                setIsConnected(false);
                setIsMicrophoneReady(
                  false,
                );
                setIsListening(false);
              }
            }

            resolveOnce();
          };
        },
      );
    }, [
      getSessionId,
      getWebSocketUrl,
      handleWebSocketEvent,
      safeSet,
    ]);

  /*
   * ============================================================
   * UI ACTIONS
   * ============================================================
   */

  const handleClose =
    useCallback(() => {
      cleanup();

      onClose();
    }, [cleanup, onClose]);

  const handleSendTranscript =
    useCallback(() => {
      const text =
        transcript.trim();

      if (!text) {
        return;
      }

      onTranscript(text);

      handleClose();
    }, [
      handleClose,
      onTranscript,
      transcript,
    ]);

  /*
   * ============================================================
   * LIFECYCLE
   * ============================================================
   */

  useEffect(() => {
    mountedRef.current = true;

    lifecycleIdRef.current += 1;

    console.info(
      "[Voice] VoiceMode mounted",
      {
        sessionId,
      },
    );

    void connectWebSocket();

    return () => {
      mountedRef.current = false;

      cleanup();
    };
  }, [
    cleanup,
    connectWebSocket,
    sessionId,
  ]);

  return (
    <div className="fixed inset-0 z-[100] flex flex-col bg-[#0e1117] text-white">
      <div className="flex items-center justify-between border-b border-[#30363d] px-5 py-4">
        <div>
          <h1 className="text-lg font-semibold">
            Voice Mode
          </h1>

          <p className="text-xs text-gray-500">
            DocTubeAI
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs text-gray-500">
            <span
              className={`h-2 w-2 rounded-full ${
                isConnected
                  ? "bg-green-500"
                  : "bg-gray-600"
              }`}
            />

            {isConnected
              ? "Connected"
              : "Disconnected"}
          </div>

          <button
            type="button"
            onClick={handleClose}
            aria-label="Close voice mode"
            className="flex h-10 w-10 items-center justify-center rounded-full text-gray-400 transition hover:bg-[#1a1d24] hover:text-white"
          >
            ✕
          </button>
        </div>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center overflow-y-auto px-6 py-8">
        <div
          className={`relative flex h-32 w-32 items-center justify-center rounded-full bg-blue-600 shadow-[0_0_80px_rgba(37,99,235,0.35)] ${
            isListening ||
            isAssistantSpeaking
              ? "animate-pulse"
              : ""
          }`}
        >
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-blue-500 text-3xl">
            🎙
          </div>
        </div>

        <div className="mt-10 text-center">
          <h2 className="text-xl font-medium">
            {!isConnected
              ? "Connecting..."
              : !isMicrophoneReady
                ? "Starting microphone..."
                : isAssistantSpeaking
                  ? "Assistant speaking..."
                  : assistantStatus ||
                    (isProcessing
                      ? "Processing..."
                      : isListening
                        ? "Listening..."
                        : "Voice Mode")}
          </h2>

          {error && (
            <p className="mt-3 max-w-md text-sm text-red-400">
              {error}
            </p>
          )}
        </div>

        <div className="mt-8 min-h-[160px] max-h-[300px] w-full max-w-2xl overflow-y-auto rounded-2xl border border-[#30363d] bg-[#161b22] px-6 py-5">
          {liveTranscript ? (
            <div>
              <p className="mb-3 text-xs text-gray-500">
                Live transcription
              </p>

              <p className="whitespace-pre-wrap text-lg leading-relaxed text-gray-200">
                {liveTranscript}
              </p>
            </div>
          ) : (
            <p className="text-center text-gray-500">
              {isAssistantSpeaking
                ? "DocTubeAI is speaking..."
                : "Speak naturally."}

              <br />

              {isAssistantSpeaking
                ? "You can interrupt the assistant."
                : "Your microphone stays on during Voice Mode."}
            </p>
          )}
        </div>

        {transcript && (
          <div className="mt-5 w-full max-w-2xl rounded-2xl border border-[#30363d] bg-[#161b22] px-6 py-5">
            <p className="mb-3 text-xs text-gray-500">
              Latest user turn
            </p>

            <p className="whitespace-pre-wrap text-lg leading-relaxed text-gray-200">
              {transcript}
            </p>
          </div>
        )}

        {assistantResponse && (
          <div className="mt-5 w-full max-w-2xl rounded-2xl border border-[#30363d] bg-[#161b22] px-6 py-5">
            <p className="mb-3 text-xs text-gray-500">
              DocTubeAI
            </p>

            <p className="whitespace-pre-wrap text-lg leading-relaxed text-gray-200">
              {assistantResponse}
            </p>
          </div>
        )}
      </div>

      <div className="flex flex-col items-center gap-4 px-5 py-8">
        <div className="flex items-center gap-3 text-sm text-gray-500">
          <span
            className={`h-3 w-3 rounded-full ${
              isMicrophoneReady
                ? "animate-pulse bg-green-500"
                : "bg-gray-600"
            }`}
          />

          {isMicrophoneReady
            ? isAssistantSpeaking
              ? "Microphone paused"
              : "Microphone active"
            : "Microphone inactive"}
        </div>

        {transcript &&
          !isProcessing &&
          !isAssistantSpeaking && (
            <button
              type="button"
              onClick={handleSendTranscript}
              className="rounded-xl bg-blue-600 px-6 py-3 font-medium transition hover:bg-blue-700"
            >
              Use this transcript ↑
            </button>
          )}
      </div>
    </div>
  );
}