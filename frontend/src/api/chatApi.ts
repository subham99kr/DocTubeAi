import { streamChatResponse } from "../services/sse.service";

type AskChatParams = {
  sessionId: string;
  query: string;
  token?: string;
  onStatus?: (status: string) => void;
  onToken?: (token: string) => void;
  onDone?: () => void;
};

export async function askChat({
  sessionId,
  query,
  token,
  onStatus,
  onToken,
  onDone,
}: AskChatParams) {
  return streamChatResponse({
    sessionId,
    query,
    token,
    onStatus,
    onToken,
    onDone,
  });
}