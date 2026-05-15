import {
  useState,
  memo,
} from "react";

import MarkdownRenderer from "./MarkdownRenderer";

import {
  Copy,
  Check,
} from "lucide-react";

import type { Message } from "../../types/chat.types";

type Props = {
  message: Message;
};

function ChatMessage({
  message,
}: Props) {
  const [copied, setCopied] =
    useState(false);

  const isUser =
    message.role === "user";

  const isStreaming =
    message.streaming;

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(
        message.content
      );

      setCopied(true);

      setTimeout(() => {
        setCopied(false);
      }, 1500);
    } catch (error) {
      console.error(
        "Copy failed:",
        error
      );
    }
  }

  return (
    <div
      className={`flex w-full min-w-0 ${
        isUser
          ? "justify-end"
          : "justify-start"
      }`}
    >
      <div
        className={`relative w-fit max-w-[92%] sm:max-w-[85%] lg:max-w-3xl rounded-2xl overflow-hidden border transition-all duration-300 ${
          isUser
            ? "bg-blue-500/15 border-blue-400/20"
            : "bg-[#161b22]/80 border-white/10"
        } ${
          !isStreaming
            ? "backdrop-blur-xl"
            : ""
        }`}
      >
        {/* Glow */}
        {!isStreaming && (
          <div className="absolute inset-0 opacity-0 hover:opacity-100 transition duration-300 bg-gradient-to-r from-blue-500/5 via-cyan-500/5 to-purple-500/5 pointer-events-none" />
        )}

        {/* Content */}
        <div className="px-4 py-3 overflow-hidden">
          {isStreaming ? (
            // LIGHTWEIGHT STREAM RENDER
            <div className="whitespace-pre-wrap break-words text-sm leading-7 text-white">
              {message.content}

              {/* Cursor */}
              <span className="inline-block w-[8px] h-[18px] ml-1 rounded-sm bg-cyan-400 animate-pulse align-middle" />
            </div>
          ) : (
            // FULL MARKDOWN RENDER
            <MarkdownRenderer
              content={
                message.content
              }
            />
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end px-4 pb-3">
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition"
          >
            {copied ? (
              <>
                <Check size={14} />
                Copied
              </>
            ) : (
              <>
                <Copy size={14} />
                Copy
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

export default memo(ChatMessage);