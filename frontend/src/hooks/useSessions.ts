import { useEffect, useState } from "react";

import { useParams } from "react-router-dom";

import { loadHome } from "../api/homeApi";

import { loadHistory } from "../api/historyApi";

import { useAuth } from "../context/AuthContext";

import { useChat } from "../context/ChatContext";

export function useSessions() {
  const { token } = useAuth();

  const {
    setMessages,
    setUploadedPdfs,
    setUrls,

    sessionId,
    setSessionId,

    sessions,
    setSessions,
  } = useChat();

  /*
   * Read session ID directly from the URL.
   *
   * Example:
   *
   * /chats/history/4bf7e2a4-db9f-4ccb-ad70-2d32026aeb9d
   *
   * urlSessionId =
   * 4bf7e2a4-db9f-4ccb-ad70-2d32026aeb9d
   */
  const { sessionId: urlSessionId } = useParams<{
    sessionId: string;
  }>();

  const [loading, setLoading] = useState(false);

  /*
   * =========================================================
   * LOAD SESSION LIST
   * =========================================================
   *
   * This only loads the sidebar sessions.
   *
   * It does NOT change the URL.
   *
   * It does NOT switch sessions.
   */
  useEffect(() => {
    fetchSessions();
  }, [token]);

  /*
   * =========================================================
   * URL -> ACTIVE SESSION
   * =========================================================
   *
   * This runs only when the URL session ID changes.
   *
   * Example:
   *
   * User clicks:
   *
   * /chats/history/ABC
   *
   * React Router changes urlSessionId to ABC.
   *
   * Then we load ABC.
   *
   * IMPORTANT:
   *
   * We do NOT navigate here.
   */
  useEffect(() => {
    if (!urlSessionId) {
      return;
    }

    /*
     * Already loaded.
     *
     * This prevents loading the same session
     * again when sessionId is updated.
     */
    if (urlSessionId === sessionId) {
      return;
    }

    switchSession(urlSessionId);
  }, [urlSessionId]);

  /*
   * =========================================================
   * FETCH SESSION LIST
   * =========================================================
   */

  async function fetchSessions() {
    try {
      setLoading(true);

      const data = await loadHome(token || undefined);

      console.log("Loaded Sessions:", data);

      setSessions((prev) => {
        const incoming = data.sessions || [];

        /*
         * Preserve the current temporary
         * "New Chat" if it has not been
         * persisted yet.
         */
        const tempSession = prev.find(
          (session) =>
            session.session_id === sessionId && session.title === "New Chat",
        );

        if (tempSession) {
          return [
            tempSession,

            ...incoming.filter(
              (session: any) => session.session_id !== tempSession.session_id,
            ),
          ];
        }

        return incoming;
      });
    } catch (error) {
      console.error("Failed loading sessions:", error);
    } finally {
      setLoading(false);
    }
  }

  /*
   * =========================================================
   * LOAD ONE SESSION
   * =========================================================
   */

  async function switchSession(id: string) {
    try {
      setLoading(true);

      console.log("Switching session:", id);

      const data = await loadHistory(id, token || undefined);

      console.log("Loaded Session:", data);

      /*
       * Update ChatContext.
       *
       * IMPORTANT:
       *
       * We do NOT navigate here.
       *
       * URL was already changed by Sidebar.
       */
      setSessionId(data.session_id);

      setMessages(data.history || []);

      setUploadedPdfs(data.pdfs_uploaded || []);

      const mappedUrls = (data.url_links || []).map((item: any) => item.title);

      setUrls(mappedUrls);

      sessionStorage.setItem("history_loaded", "true");
    } catch (error) {
      console.error("Failed switching session:", error);
    } finally {
      setLoading(false);
    }
  }

  return {
    sessions,
    loading,
    fetchSessions,
    switchSession,
  };
}
