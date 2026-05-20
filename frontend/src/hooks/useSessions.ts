import {
  useEffect,
  useState,
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
    sessionId,
    setSessionId,

    sessions,
    setSessions,
  } = useChat();

  const [loading, setLoading] =
    useState(false);



  useEffect(() => {
        fetchSessions();
  }, [token]);

  async function fetchSessions() {
    try {
      setLoading(true);

      const data =
        await loadHome(
          token || undefined
        );

      console.log(
        "Loaded Sessions:",
        data
      );

      // setSessions(
      //   data.sessions || []
      // );



    setSessions((prev) => {

      const incoming =
        data.sessions || [];

      // current active temp chat
      const tempSession =
        prev.find(
          (session) =>
            session.session_id ===
              sessionId &&
            session.title ===
              "New Chat"
        );

      // preserve ONLY active temp chat
      if (tempSession) {
        return [
          tempSession,
          ...incoming,
        ];
      }

      return incoming;
    });







    } catch (error) {
      console.error(
        "Failed loading sessions:",
        error
      );
    } finally {
      setLoading(false);
    }
  }

  async function switchSession(
    sessionId: string
  ) {
    try {
      setLoading(true);

      const data =
        await loadHistory(
          sessionId,
          token || undefined
        );

      console.log(
        "Loaded Session:",
        data
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

      // scroll to bottom instantly
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
