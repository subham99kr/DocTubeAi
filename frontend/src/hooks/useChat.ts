import { askChat } from "../api/chatApi";
import { useChat as useChatContext } from "../context/ChatContext";
import { useAuth } from "../context/AuthContext";
import { useNavigate } from "react-router-dom";

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
  const navigate = useNavigate();


  async function sendMessage(query: string) {
    if (!query.trim() || loading) return;

    setLoading(true);

    let finalResponse = "";

    let timeoutId: ReturnType<typeof setTimeout> | null = null;

    let inactivityTimer: ReturnType<typeof setTimeout> | null = null;

    const stopStreaming = () => {
      setMessages((prev) => {
        const updated = [...prev];
        const last = updated.length - 1;

        if (updated[last]?.role === "assistant")
          updated[last] = {
            ...updated[last],
            content: finalResponse,
            streaming: false,
          };

        return updated;
      });

      setLoading(false);

      setTimeout(() => setStatus(""), 800);
    };

    const resetInactivityTimer = () => {
      if (inactivityTimer) clearTimeout(inactivityTimer);

      inactivityTimer = setTimeout(() => {
        console.warn("Force closing inactive stream");
        stopStreaming();
      }, 2000);
    };

    const currentSession = sessions.find(
      (s) => s.session_id === sessionId
    );

    if (currentSession?.title === "New Chat") {
      const title =
        query.length > 30
          ? query.slice(0, 30) + "..."
          : query;

      setSessions((prev) =>
        prev.map((session) =>
          session.session_id === sessionId
            ? { ...session, title }
            : session
        )
      );
      
    }

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
      resetInactivityTimer();

      await askChat({
        sessionId,
        query,
        token: token || undefined,

        onStatus(statusMessage) {
          resetInactivityTimer();
          setStatus(statusMessage);
        },

        onToken(tokenChunk) {
          resetInactivityTimer();

          finalResponse += tokenChunk;

          finalResponse = finalResponse.replace(
            /`\s*`\s*`/g,
            "```"
          );

          if (timeoutId) return;

          timeoutId = setTimeout(() => {
            setMessages((prev) => {
              const updated = [...prev];

              updated[updated.length - 1] = {
                role: "assistant",
                content: finalResponse,
                streaming: true,
              };

              return updated;
            });

            timeoutId = null;
          }, 35);
        },

        onDone() {
          console.log("STREAM DONE");

          if (inactivityTimer)
            clearTimeout(inactivityTimer);

          stopStreaming();

          //silently navigate to that link
          navigate(
            `/chats/history/${sessionId}`,
            { replace: true }
          );

        },
      });
    } catch (error) {
      console.error("CHAT ERROR:", error);

      if (inactivityTimer)
        clearTimeout(inactivityTimer);

      setLoading(false);

      setStatus("Error generating response");

      setTimeout(() => setStatus(""), 2000);
    }
  }

  return {
    messages,
    loading,
    status,
    sendMessage,
  };
}
