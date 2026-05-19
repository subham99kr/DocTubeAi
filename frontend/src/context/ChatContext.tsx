import {
  createContext,
  useContext,
  useState,
} from "react";

import type { ReactNode } from "react";

// IMPORT SHARED MESSAGE TYPE
import type { Message }
from "../types/chat.types";

export type Session = {
  session_id: string;
  title?: string;
};

type ChatContextType = {
  messages: Message[];

  setMessages: React.Dispatch<
    React.SetStateAction<Message[]>
  >;

  sessionId: string;

  setSessionId: React.Dispatch<
    React.SetStateAction<string>
  >;

  loading: boolean;

  setLoading: React.Dispatch<
    React.SetStateAction<boolean>
  >;

  uploadedPdfs: string[];

  setUploadedPdfs: React.Dispatch<
    React.SetStateAction<string[]>
  >;

  urls: string[];

  setUrls: React.Dispatch<
    React.SetStateAction<string[]>
  >;

  // SESSIONS
  sessions: Session[];

  setSessions: React.Dispatch<
    React.SetStateAction<Session[]>
  >;

  // STREAM STATUS
  status: string;

  setStatus: React.Dispatch<
    React.SetStateAction<string>
  >;
};

const ChatContext =
  createContext<ChatContextType | null>(
    null
  );

type Props = {
  children: ReactNode;
};

function generateSessionId(): string {
  return crypto.randomUUID();
}

// INITIAL CHAT
const initialSessionId =
  generateSessionId();

const initialSession: Session = {
  session_id:
    initialSessionId,

  title: "New Chat",
};

export function ChatProvider({
  children,
}: Props) {
  const [messages, setMessages] =
    useState<Message[]>([]);

  // ACTIVE SESSION
  const [sessionId, setSessionId] =
    useState(
      initialSessionId
    );

  const [loading, setLoading] =
    useState(false);

  const [
    uploadedPdfs,
    setUploadedPdfs,
  ] = useState<string[]>([]);

  const [urls, setUrls] =
    useState<string[]>(
      []
    );

  // SESSION LIST STARTS WITH NEW CHAT
  const [sessions, setSessions] =
    useState<Session[]>([
      initialSession,
    ]);

  // STREAM STATUS
  const [status, setStatus] =
    useState("");

  return (
    <ChatContext.Provider
      value={{
        messages,
        setMessages,

        sessionId,
        setSessionId,

        loading,
        setLoading,

        uploadedPdfs,
        setUploadedPdfs,

        urls,
        setUrls,

        sessions,
        setSessions,

        status,
        setStatus,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
}

export function useChat() {
  const context =
    useContext(ChatContext);

  if (!context) {
    throw new Error(
      "useChat must be used inside ChatProvider"
    );
  }

  return context;
}