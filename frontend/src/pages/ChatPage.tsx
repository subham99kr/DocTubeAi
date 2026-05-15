import { useState } from "react";

import ChatWindow from "../components/chat/ChatWindow";

import ChatInput from "../components/chat/ChatInput";

import { useChat } from "../context/ChatContext";

import { useAuth } from "../context/AuthContext";

import { askChat } from "../api/chatApi";

export default function ChatPage() {
  const {
    setMessages,
    sessionId,
    loading,
    setLoading,
  } = useChat();

  const { token } = useAuth();

  const [streamingMessage, setStreamingMessage] =
    useState("");

  async function handleSend(message: string) {
    setLoading(true);

    setStreamingMessage("");

    setMessages((prev) => [
      ...prev,
      {
        role: "user",
        content: message,
      },
    ]);

    let fullResponse = "";

    try {
      await askChat({
        sessionId,
        query: message,
        token: token || undefined,

        onToken(tokenChunk) {
          fullResponse += tokenChunk;

          setStreamingMessage(fullResponse);
        },

        onDone() {
          setMessages((prev) => [
            ...prev,
            {
              role: "assistant",
              content: fullResponse,
            },
          ]);

          setStreamingMessage("");

          setLoading(false);
        },
      });
    } catch (error) {
      console.error(error);

      setLoading(false);
    }
  }

  return (
    <div className="h-screen bg-[#0e1117] text-white flex flex-col">
      <div className="border-b border-[#30363d] p-4">
        <h1 className="text-xl font-bold">
          DocTubeAI
        </h1>
      </div>

      <div className="flex-1 overflow-hidden">
        <ChatWindow />

        {streamingMessage && (
          <div className="px-4 pb-4">
            <div className="max-w-3xl px-4 py-3 rounded-2xl border bg-[#1a1d24] border-[#30363d]">
              {streamingMessage}
            </div>
          </div>
        )}
      </div>

      <ChatInput
        onSend={handleSend}
        disabled={loading}
      />
    </div>
  );
}
