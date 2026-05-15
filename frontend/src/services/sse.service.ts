export type StreamEvent =
  | {
      type: "status";
      data: string;
    }
  | {
      type: "token";
      data: string;
    }
  | {
      type: "done";
      data?: string;
    };

type StreamParams = {
  sessionId: string;
  query: string;
  token?: string;

  onStatus?: (
    status: string
  ) => void;

  onToken?: (
    token: string
  ) => void;

  onDone?: () => void;
};

const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL;

export async function streamChatResponse({
  sessionId,
  query,
  token,
  onStatus,
  onToken,
  onDone,
}: StreamParams) {
  const response = await fetch(
    `${BACKEND_URL}/chats/ask/stream`,
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",

        ...(token
          ? {
              Authorization: `Bearer ${token}`,
            }
          : {}),
      },

      body: JSON.stringify({
        session_id: sessionId,
        query,
      }),
    }
  );

  if (!response.body) {
    throw new Error(
      "No response body"
    );
  }

  const reader =
    response.body.getReader();

  const decoder =
    new TextDecoder();

  let buffer = "";

  // TOKEN BUFFER
  let tokenBuffer = "";

  // STREAM FLUSH TIMER
  let flushTimeout:
    | ReturnType<
        typeof setTimeout
      >
    | null = null;

  // FLUSH TOKENS SMOOTHLY
  function flushTokens() {
    if (!tokenBuffer) {
      return;
    }

    onToken?.(tokenBuffer);

    tokenBuffer = "";

    flushTimeout = null;
  }

  while (true) {
    const { done, value } =
      await reader.read();

    // STREAM ENDED
    if (done) {
      flushTokens();

      onDone?.();

      break;
    }

    buffer += decoder.decode(
      value,
      {
        stream: true,
      }
    );

    const lines =
      buffer.split("\n");

    buffer = lines.pop() || "";

    for (const line of lines) {
      if (
        !line.startsWith(
          "data: "
        )
      ) {
        continue;
      }

      try {
        const json =
          JSON.parse(
            line.replace(
              "data: ",
              ""
            )
          );

        // IGNORE HEARTBEATS
        if (
          json.type ===
          "heartbeat"
        ) {
          continue;
        }

        // STATUS EVENTS
        if (
          json.type ===
          "status"
        ) {
          onStatus?.(
            json.data
          );

          continue;
        }

        // TOKEN EVENTS
        if (
          json.type ===
          "token"
        ) {
          tokenBuffer +=
            json.data;

          // already scheduled
          if (
            flushTimeout
          ) {
            continue;
          }

          // BATCH TOKENS
          flushTimeout =
            setTimeout(
              flushTokens,
              35
            );

          continue;
        }

        // DONE EVENT
        if (
          json.type ===
          "done"
        ) {
          flushTokens();

          onDone?.();

          return;
        }
      } catch (error) {
        console.error(
          "SSE Parse Error:",
          error
        );
      }
    }
  }
}