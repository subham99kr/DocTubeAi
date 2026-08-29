export type VoiceWebSocketEvent =
  | {
      type: "ready";
    }
  | {
      type: "transcribing";
    }
  | {
      type: "transcript";
      text: string;
    }
  | {
      type: "thinking";
    }
  | {
      type: "token";
      data?: string;
      content?: string;
    }
  | {
      type: "done";
      data?: unknown;
    }
  | {
      type: "turn_complete";
    }
  | {
      type: "error";
      message: string;
    }
  | {
      type: string;
      [key: string]: unknown;
    };

type VoiceWebSocketCallbacks = {
  onOpen?: () => void;

  onEvent?: (event: VoiceWebSocketEvent) => void;

  onError?: (error: Error) => void;

  onClose?: () => void;
};

export class VoiceWebSocketService {
  private socket: WebSocket | null = null;

  private callbacks: VoiceWebSocketCallbacks = {};

  connect(
    sessionId: string,
    callbacks: VoiceWebSocketCallbacks = {},
  ): Promise<void> {
    this.callbacks = callbacks;

    return new Promise((resolve, reject) => {
      const backendUrl =
        import.meta.env.VITE_PUBLIC_BACKEND_URL ||
        import.meta.env.VITE_BACKEND_URL ||
        "http://127.0.0.1:8000";

      const wsUrl =
        backendUrl.replace(/^http:/, "ws:").replace(/^https:/, "wss:") +
        `/voice/ws`;

      console.log("🔌 Connecting Voice WebSocket:", wsUrl);

      this.socket = new WebSocket(wsUrl);

      this.socket.binaryType = "arraybuffer";

      this.socket.onopen = () => {
        console.log("✅ Voice WebSocket connected");

        this.sendJson({
          type: "start",
          session_id: sessionId,
        });

        this.callbacks.onOpen?.();

        resolve();
      };

      this.socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          console.log("📨 Voice WS event:", data);

          this.callbacks.onEvent?.(data);
        } catch (error) {
          console.error("❌ Invalid WebSocket message:", error);
        }
      };

      this.socket.onerror = () => {
        const error = new Error("Voice WebSocket connection failed.");

        this.callbacks.onError?.(error);

        reject(error);
      };

      this.socket.onclose = () => {
        console.log("🔌 Voice WebSocket closed");

        this.callbacks.onClose?.();

        this.socket = null;
      };
    });
  }

  sendAudio(blob: Blob): void {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      console.warn("⚠️ WebSocket is not open.");

      return;
    }

    this.socket.send(blob);
  }

  stopTurn(): void {
    this.sendJson({
      type: "stop",
    });
  }

  ping(): void {
    this.sendJson({
      type: "ping",
    });
  }

  close(): void {
    if (!this.socket) {
      return;
    }

    if (this.socket.readyState === WebSocket.OPEN) {
      this.socket.close();
    }

    this.socket = null;
  }

  isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  private sendJson(data: unknown): void {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      return;
    }

    this.socket.send(JSON.stringify(data));
  }
}
