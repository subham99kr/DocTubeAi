import {
  useEffect,
  useRef,
  memo,
} from "react";

import { useChat } from "../../context/ChatContext";

import ChatMessage from "./ChatMessage";

import StreamingMessage from "./StreamingMessage";

import {
  motion,
  AnimatePresence,
} from "framer-motion";

function ChatWindow() {
  const { messages } = useChat();

  const scrollRef =
    useRef<HTMLDivElement>(null);

  const firstLoadRef =
    useRef(true);

  // SMART AUTO SCROLL
  useEffect(() => {
    const container =
      scrollRef.current;

    if (!container) {
      return;
    }

    const lastMessage =
      messages[
        messages.length - 1
      ];

    const isStreaming =
      lastMessage?.streaming;

    const nearBottom =
      container.scrollHeight -
        container.scrollTop -
        container.clientHeight <
      120;

    const historyLoaded =
      sessionStorage.getItem(
        "history_loaded"
      );

    if (
      isStreaming ||
      nearBottom ||
      historyLoaded
    ) {
      requestAnimationFrame(() => {
        container.scrollTo({
          top:
            container.scrollHeight,

          behavior:
            firstLoadRef.current ||
            isStreaming ||
            historyLoaded
              ? "auto"
              : "smooth",
        });

        firstLoadRef.current =
          false;

        if (
          historyLoaded
        ) {
          sessionStorage.removeItem(
            "history_loaded"
          );
        }
      });
    }
  }, [messages]);

  return (
    <div
      ref={scrollRef}
      className="relative flex flex-col gap-4 p-4 overflow-y-auto h-full min-w-0"
    >
      <AnimatePresence
        initial={false}
      >
        {messages.map(
          (message, index) => {
            const isStreaming =
              message.streaming;

            if (isStreaming) {
              return (
                <StreamingMessage
                  key={`stream-${index}`}
                  content={
                    message.content
                  }
                />
              );
            }

            return (
              <motion.div
                key={`${message.role}-${index}-${message.content.length}`}
                initial={{
                  opacity: 0,
                  y: 10,
                }}
                animate={{
                  opacity: 1,
                  y: 0,
                }}
                exit={{
                  opacity: 0,
                }}
                transition={{
                  duration: 0.18,
                }}
                layout={false}
              >
                <ChatMessage
                  message={
                    message
                  }
                />
              </motion.div>
            );
          }
        )}
      </AnimatePresence>
    </div>
  );
}

export default memo(ChatWindow);