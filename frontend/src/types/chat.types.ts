export type MessageRole =
  | "user"
  | "assistant";

export interface Message {
  role: MessageRole;

  content: string;

  // STREAMING STATE
  streaming?: boolean;
}

export interface StreamChunk {
  type:
    | "status"
    | "token"
    | "done";

  data: string;
}