import type { Message } from "./chat.types";

export interface Session {
  session_id: string;
  title?: string;
}

export interface UrlLink {
  url: string;
  title: string;
  added_at?: string;
}

export interface SessionHistoryResponse {
  session_id: string;

  history: Message[];

  pdfs_uploaded: string[];

  url_links: UrlLink[];
}