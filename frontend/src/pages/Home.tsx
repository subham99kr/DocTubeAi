import {
  useEffect,
} from "react";

import {
  useSearchParams,
  useParams,
} from "react-router-dom";

import MainLayout from "../layouts/MainLayout";

import ChatWindow from "../components/chat/ChatWindow";

import ChatInput from "../components/chat/ChatInput";

import AnimatedBackground from "../components/ui/AnimatedBackground";

import { useChat } from "../hooks/useChat";

import { exchangeCodeForToken } from "../api/authApi";

import { useAuth } from "../context/AuthContext";

import { useChat as useChatContext }
from "../context/ChatContext";

import { useSessions } from "../hooks/useSessions";

export default function Home() {
  const {
    sendMessage,
    loading,
  } = useChat();

  const { login } = useAuth();

  const { status } =
    useChatContext();

  const {
    switchSession,
  } = useSessions();

  const [searchParams] =
    useSearchParams();

  const { sessionId } =
    useParams();

  // LOAD CHAT FROM URL
  useEffect(() => {
    if (sessionId) {
      switchSession(
        sessionId
      );
    }
  }, [sessionId]);

  // Handle OAuth redirect
  useEffect(() => {
    async function authenticate() {
      const code =
        searchParams.get("code");

      const authProcessed =
        sessionStorage.getItem(
          "auth_processed"
        );

      if (
        !code ||
        authProcessed
      ) {
        return;
      }

      sessionStorage.setItem(
        "auth_processed",
        "true"
      );

      try {
        const data =
          await exchangeCodeForToken(
            code
          );

        login(
          data.access_token,
          data.user
        );

        window.history.replaceState(
          {},
          document.title,
          "/"
        );
      } catch (error) {
        console.error(
          "OAuth Failed:",
          error
        );

        sessionStorage.removeItem(
          "auth_processed"
        );
      }
    }

    authenticate();
  }, []);

  return (
    <MainLayout>
      <div className="h-full flex flex-col bg-[#0e1117] text-white min-h-0 relative overflow-hidden">
        <AnimatedBackground />

        {/* Header */}
        <div className="border-b border-[#30363d]/60 backdrop-blur-md bg-black/10 p-4 shrink-0 relative z-10">
          <h1 className="text-xl sm:text-2xl font-bold truncate">
            DocTubeAI
          </h1>

          <p className="text-xs sm:text-sm text-gray-400 mt-1">
            Multi-source AI RAG Assistant
          </p>
        </div>

        {/* Chat Window */}
        <div className="flex-1 overflow-hidden min-h-0 relative z-10">
          <ChatWindow />
        </div>

        {/* Status */}
        {status && (
          <div className="px-4 py-2 text-xs text-cyan-300 relative z-10 backdrop-blur-sm bg-black/10 border-t border-white/5">
            ✨ {status}
          </div>
        )}

        {/* Chat Input */}
        <div className="shrink-0 relative z-10">
          <ChatInput
            onSend={sendMessage}
            disabled={loading}
          />
        </div>
      </div>
    </MainLayout>
  );
}