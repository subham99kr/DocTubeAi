import { askChat } from "../api/chatApi";

import { useChat as useChatContext } from "../context/ChatContext";

import { useAuth } from "../context/AuthContext";

export function useChat() {
  const {
    sessionId,

    messages,
    setMessages,

    loading,
    setLoading,

    sessions,
    setSessions,

    status,
    setStatus,
  } = useChatContext();

  const { token } = useAuth();

  async function sendMessage(
    query: string
  ) {
    if (!query.trim()) {
      return;
    }

    if (loading) {
      return;
    }

    setLoading(true);

    let finalResponse = "";

    // THROTTLE BUFFER
    let timeoutId:
      | ReturnType<
          typeof setTimeout
        >
      | null = null;

    // Rename temporary chat
    const currentSession =
      sessions.find(
        (s) =>
          s.session_id ===
          sessionId
      );

    if (
      currentSession?.title ===
      "New Chat"
    ) {
      const title =
        query.length > 30
          ? query.slice(0, 30) +
            "..."
          : query;

      setSessions((prev) =>
        prev.map((session) =>
          session.session_id ===
          sessionId
            ? {
                ...session,
                title,
              }
            : session
        )
      );
    }

    // Add user + assistant placeholder
    setMessages((prev) => [
      ...prev,

      {
        role: "user",
        content: query,
      },

      {
        role: "assistant",
        content: "",
        streaming: true,
      },
    ]);

    try {
      await askChat({
        sessionId,
        query,
        token:
          token || undefined,

        // STATUS EVENTS
        onStatus(
          statusMessage
        ) {
          setStatus(
            statusMessage
          );
        },

        // TOKEN STREAM
        onToken(tokenChunk) {
          finalResponse +=
            tokenChunk;

          // normalize markdown fences
          finalResponse =
            finalResponse.replace(
              /`\s*`\s*`/g,
              "```"
            );

          // already scheduled
          if (timeoutId) {
            return;
          }

          // THROTTLED UI UPDATE
          timeoutId = setTimeout(
            () => {
              setMessages(
                (prev) => {
                  const updated =
                    [...prev];

                  updated[
                    updated.length -
                      1
                  ] = {
                    role:
                      "assistant",
                    content:
                      finalResponse,
                    streaming: true,
                  };

                  return updated;
                }
              );

              timeoutId = null;
            },
            35
          );
        },

        // STREAM DONE
        onDone() {
          // flush final render
          setMessages((prev) => {
            const updated = [
              ...prev,
            ];

            const last =
              updated.length - 1;

            if (
              updated[last]
                ?.role ===
              "assistant"
            ) {
              updated[last] = {
                ...updated[last],
                content:
                  finalResponse,
                streaming: false,
              };
            }

            return updated;
          });

          setLoading(false);

          setTimeout(() => {
            setStatus("");
          }, 800);
        },
      });
    } catch (error) {
      console.error(
        "CHAT ERROR:",
        error
      );

      setLoading(false);

      setStatus(
        "Error generating response"
      );

      setTimeout(() => {
        setStatus("");
      }, 2000);
    }
  }

  return {
    messages,
    loading,
    status,
    sendMessage,
  };
}