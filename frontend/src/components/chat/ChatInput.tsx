import { useState, useRef, useEffect } from "react";

import PdfUploader from "../context/PdfUploader";
import UrlInput from "../context/UrlInput";
import VoiceMode from "./VoiceMode";

type Props = {
  onSend: (message: string) => void;
  disabled?: boolean;
};

export default function ChatInput({ onSend, disabled = false }: Props) {
  const [input, setInput] = useState("");
  const [showPopover, setShowPopover] = useState(false);
  const [showVoiceMode, setShowVoiceMode] = useState(false);

  const popoverRef = useRef<HTMLDivElement | null>(null);

  /*
   * Submit normal text message.
   */
  function handleSubmit() {
    const message = input.trim();

    if (!message) {
      return;
    }

    onSend(message);
    setInput("");
  }

  /*
   * Add voice transcript to the
   * existing input.
   */
  function handleTranscript(text: string) {
    const transcript = text.trim();

    if (!transcript) {
      return;
    }

    setInput((current) => {
      const separator = current.trim().length > 0 ? " " : "";

      return current + separator + transcript;
    });
  }

  /*
   * Close attachment popover
   * when clicking outside.
   */
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(event.target as Node)
      ) {
        setShowPopover(false);
      }
    }

    document.addEventListener("mousedown", handleClickOutside);

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, []);

  /*
   * Voice Mode is a full-screen
   * component.
   *
   * When this becomes true:
   *
   * ChatInput
   *      ↓
   * VoiceMode mounts
   *      ↓
   * VoiceMode automatically
   * starts microphone
   */
  if (showVoiceMode) {
    return (
      <VoiceMode
        onClose={() => {
          setShowVoiceMode(false);
        }}
        onTranscript={handleTranscript}
      />
    );
  }

  return (
    <div
      className="
        border-t
        border-[#30363d]
        px-2
        sm:px-4
        lg:px-6
        py-4
        bg-[#0e1117]
      "
    >
      <div
        className="
          relative
          max-w-4xl
          mx-auto
        "
      >
        {/* ================================= */}
        {/* Attachment Popover */}
        {/* ================================= */}

        {showPopover && (
          <div
            ref={popoverRef}
            className="
              absolute
              bottom-16
              left-0
              w-[95vw]
              sm:w-[340px]
              max-w-[340px]
              rounded-2xl
              border
              border-[#30363d]
              bg-[#161b22]/95
              backdrop-blur-xl
              shadow-2xl
              p-4
              z-50
            "
          >
            <div
              className="
                flex
                flex-col
                gap-6
              "
            >
              {/* PDF Upload */}

              <div>
                <h3
                  className="
                    text-sm
                    font-semibold
                    mb-3
                  "
                >
                  Upload PDFs
                </h3>

                <PdfUploader />
              </div>

              {/* YouTube Context */}

              <div>
                <h3
                  className="
                    text-sm
                    font-semibold
                    mb-3
                  "
                >
                  Add YouTube Context
                </h3>

                <UrlInput />
              </div>
            </div>
          </div>
        )}

        {/* ================================= */}
        {/* Input Container */}
        {/* ================================= */}

        <div
          className="
            flex
            items-center
            gap-2
            sm:gap-3
            bg-[#1a1d24]
            border
            border-[#30363d]
            rounded-2xl
            px-2
            sm:px-3
            py-2
            sm:py-3
          "
        >
          {/* ================================= */}
          {/* Attachment Button */}
          {/* ================================= */}

          <button
            type="button"
            onClick={() => {
              if (disabled) {
                return;
              }

              setShowPopover((current) => !current);
            }}
            disabled={disabled}
            title="Add context"
            className="
              w-10
              h-10
              shrink-0
              rounded-xl
              hover:bg-[#2a2f3a]
              transition
              flex
              items-center
              justify-center
              text-xl
              disabled:opacity-50
              disabled:cursor-not-allowed
            "
          >
            +
          </button>

          {/* ================================= */}
          {/* Voice Mode Button */}
          {/* ================================= */}

          <button
            type="button"
            onClick={() => {
              if (disabled) {
                return;
              }

              /*
               * Close attachment popover
               * before opening Voice Mode.
               */
              setShowPopover(false);

              /*
               * Opening VoiceMode causes
               * VoiceMode's useEffect() to
               * automatically start recording.
               */
              setShowVoiceMode(true);
            }}
            disabled={disabled}
            title="Voice mode"
            className="
              w-10
              h-10
              shrink-0
              rounded-xl
              hover:bg-[#2a2f3a]
              transition
              flex
              items-center
              justify-center
              text-xl
              disabled:opacity-50
              disabled:cursor-not-allowed
            "
          >
            🎙
          </button>

          {/* ================================= */}
          {/* Text Input */}
          {/* ================================= */}

          <textarea
            value={input}
            disabled={disabled}
            rows={1}
            onChange={(event) => {
              setInput(event.target.value);

              /*
               * Auto resize textarea.
               */
              event.target.style.height = "auto";
              event.target.style.height = event.target.scrollHeight + "px";
            }}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                handleSubmit();
              }
            }}
            placeholder="Ask something..."
            className="
              flex-1
              min-w-0
              bg-transparent
              outline-none
              text-white
              text-sm
              sm:text-base
              resize-none
              overflow-hidden
              max-h-40
            "
          />

          {/* ================================= */}
          {/* Send Button */}
          {/* ================================= */}

          <button
            type="button"
            onClick={handleSubmit}
            disabled={disabled || !input.trim()}
            title="Send message"
            className="
              shrink-0
              bg-blue-600
              hover:bg-blue-700
              px-4
              sm:px-5
              py-2
              rounded-xl
              transition
              disabled:opacity-50
              disabled:cursor-not-allowed
            "
          >
            ↑
          </button>
        </div>
      </div>
    </div>
  );
}
