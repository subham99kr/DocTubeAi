import { useState } from "react";

import UserProfile from "./UserProfile";

import SessionList from "./SessionList";

import { useChat } from "../../context/ChatContext";

import { useSessions } from "../../hooks/useSessions";

type Props = {
  closeMobileSidebar?: () => void;
};

export default function Sidebar({
  closeMobileSidebar,
}: Props) {
  const [collapsed, setCollapsed] =
    useState(false);

  const {
    sessionId,
    setSessionId,

    messages,
    setMessages,

    setUploadedPdfs,
    setUrls,

    sessions,
    setSessions,
  } = useChat();

  const { switchSession } =
    useSessions();

  function handleNewChat() {
    const currentSession =
      sessions.find(
        (s) =>
          s.session_id ===
          sessionId
      );

    const isTemporaryEmptyChat =
      currentSession?.title ===
        "New Chat" &&
      messages.length === 0;

    if (isTemporaryEmptyChat) {
      return;
    }

    const newSessionId =
      crypto.randomUUID();

    setSessions((prev) => [
      {
        session_id: newSessionId,
        title: "New Chat",
      },
      ...prev,
    ]);

    setSessionId(newSessionId);

    setMessages([]);

    setUploadedPdfs([]);

    setUrls([]);
  }

  return (
    <div
      className={`border-r border-[#30363d] bg-[#11141a] flex flex-col transition-all duration-300 h-full ${
        collapsed
          ? "w-[80px]"
          : "w-[280px] sm:w-[300px]"
      }`}
    >
      <div className="p-4 border-b border-[#30363d]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center text-xl shadow-lg shrink-0">
              🤖
            </div>

            {!collapsed && (
              <div className="min-w-0">
                <h2 className="font-bold text-white text-lg truncate">
                  DocTubeAI
                </h2>

                <p className="text-xs text-gray-400 truncate">
                  AI Assistant
                </p>
              </div>
            )}
          </div>

          <button
            onClick={() => {
              // Mobile / tablet
              if (
                window.innerWidth < 1024
              ) {
                closeMobileSidebar?.();
                return;
              }

              // Desktop
              setCollapsed(
                !collapsed
              );
            }}
            className="text-gray-400 hover:text-white transition-colors text-lg"
          >
            {collapsed
              ? "➡"
              : "⬅"}
          </button>
        </div>

        {!collapsed && (
          <>
            <div className="mt-4">
              <UserProfile />
            </div>

            <button
              onClick={handleNewChat}
              className="mt-4 w-full bg-blue-600 hover:bg-blue-700 py-3 rounded-xl transition-all duration-200 hover:scale-[1.02] active:scale-[0.98]"
            >
              + New Chat
            </button>
          </>
        )}
      </div>

      {!collapsed && (
        <div className="flex-1 overflow-y-auto p-3">
          <SessionList
            sessions={sessions}
            activeSessionId={
              sessionId
            }
            onSelect={(id) => {
              switchSession(id);

              closeMobileSidebar?.();
            }}
          />
        </div>
      )}
    </div>
  );
}