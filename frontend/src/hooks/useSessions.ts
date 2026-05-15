import {
  useEffect,
  useState,
  useRef,
} from "react";

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
    setSessionId,

    // GLOBAL sessions
    sessions,
    setSessions,
  } = useChat();

  const [loading, setLoading] =
    useState(false);

  // Prevent repeated fetches
  const hasFetched =
    useRef(false);

  useEffect(() => {
    if (!token) {
      setSessions([]);
      hasFetched.current = false;
      return;
    }

    // already fetched
    if (
      hasFetched.current ||
      sessions.length > 0
    ) {
      return;
    }

    hasFetched.current = true;

    fetchSessions();
  }, [token]);

  async function fetchSessions() {
    if (!token) return;

    try {
      setLoading(true);

      const data =
        await loadHome(token);

      console.log(
        "Loaded Sessions:",
        data
      );

      setSessions(
        data.sessions || []
      );
    } catch (error) {
      console.error(
        "Failed loading sessions:",
        error
      );
    } finally {
      setLoading(false);
    }
  }

  // ONLY UPDATE switchSession

  async function switchSession(
    sessionId: string
  ) {
    if (!token) return;

    try {
      setLoading(true);

      const data =
        await loadHistory(
          sessionId,
          token
        );

      setSessionId(
        data.session_id
      );

      setMessages(
        data.history || []
      );

      setUploadedPdfs(
        data.pdfs_uploaded || []
      );

      const mappedUrls = (
        data.url_links || []
      ).map(
        (item: any) =>
          item.title
      );

      setUrls(mappedUrls);

      // FORCE SCROLL FLAG
      sessionStorage.setItem(
        "history_loaded",
        "true"
      );
    } catch (error) {
      console.error(
        "Failed switching session:",
        error
      );
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