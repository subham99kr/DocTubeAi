import { useState } from "react";

import { useNavigate } from "react-router-dom";

import UserProfile from "./UserProfile";

import SessionList from "./SessionList";

import { useChat } from "../../context/ChatContext";

type Props = {
  closeMobileSidebar?: () => void;
};

export default function Sidebar({ closeMobileSidebar }: Props) {
  const [collapsed, setCollapsed] = useState(false);

  const navigate = useNavigate();

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

  /*
   * =========================================================
   * NEW CHAT
   * =========================================================
   */

  function handleNewChat() {
    const currentSession = sessions.find((s) => s.session_id === sessionId);

    /*
     * If the current session is already
     * an empty New Chat then there is
     * nothing to create.
     */
    const isTemporaryEmptyChat =
      currentSession?.title === "New Chat" && messages.length === 0;

    if (isTemporaryEmptyChat) {
      return;
    }

    /*
     * Generate a completely new session.
     */
    const newSessionId = crypto.randomUUID();

    /*
     * Add it to sidebar immediately.
     */
    setSessions((prev) => [
      {
        session_id: newSessionId,

        title: "New Chat",
      },

      ...prev,
    ]);

    /*
     * Update active session.
     */
    setSessionId(newSessionId);

    /*
     * Clear current chat.
     */
    setMessages([]);

    setUploadedPdfs([]);

    setUrls([]);

    /*
     * IMPORTANT:
     *
     * URL becomes:
     *
     * /chats/history/<newSessionId>
     *
     * No API call here.
     */
    navigate(`/chats/history/${newSessionId}`);
  }

  return (
    <div
      className={`border-r border-[#30363d] bg-[#11141a] flex flex-col transition-all duration-300 h-full ${
        collapsed ? "w-[80px]" : "w-[280px] sm:w-[300px]"
      }`}
    >
      {/* ================================================= */}
      {/* HEADER */}
      {/* ================================================= */}

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

                <p className="text-xs text-gray-400 truncate">AI Assistant</p>
              </div>
            )}
          </div>

          <button
            onClick={() => {
              /*
               * Mobile / tablet
               */
              if (window.innerWidth < 1024) {
                closeMobileSidebar?.();

                return;
              }

              /*
               * Desktop
               */
              setCollapsed(!collapsed);
            }}
            className="text-gray-400 hover:text-white transition-colors text-lg"
          >
            {collapsed ? "➡" : "⬅"}
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

      {/* ================================================= */}
      {/* SESSION LIST */}
      {/* ================================================= */}

      {!collapsed && (
        <div className="flex-1 overflow-y-auto p-3">
          <SessionList
            sessions={sessions}
            activeSessionId={sessionId}
            onSelect={(id) => {
              /*
               * IMPORTANT:
               *
               * Do NOT call:
               *
               * switchSession(id)
               *
               * here.
               *
               * Only change the URL.
               *
               * useSessions() watches the URL
               * and loads the history.
               */
              navigate(`/chats/history/${id}`);

              closeMobileSidebar?.();
            }}
          />
        </div>
      )}
    </div>
  );
}
