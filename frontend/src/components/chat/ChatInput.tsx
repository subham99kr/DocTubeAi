import { useState, useRef, useEffect } from "react";

import PdfUploader from "../context/PdfUploader";

import UrlInput from "../context/UrlInput";

type Props = {
  onSend: (message: string) => void;
  disabled?: boolean;
};

export default function ChatInput({
  onSend,
  disabled,
}: Props) {
  const [input, setInput] = useState("");

  const [showPopover, setShowPopover] =
    useState(false);

  const popoverRef =
    useRef<HTMLDivElement | null>(null);

  function handleSubmit() {
    if (!input.trim()) return;

    onSend(input);

    setInput("");
  }

  // close on outside click
  useEffect(() => {
    function handleClickOutside(
      event: MouseEvent
    ) {
      if (
        popoverRef.current &&
        !popoverRef.current.contains(
          event.target as Node
        )
      ) {
        setShowPopover(false);
      }
    }

    document.addEventListener(
      "mousedown",
      handleClickOutside
    );

    return () => {
      document.removeEventListener(
        "mousedown",
        handleClickOutside
      );
    };
  }, []);

  return (
    <div className="border-t border-[#30363d] px-2 sm:px-4 lg:px-6 py-4 bg-[#0e1117]">
      <div className="relative max-w-4xl mx-auto">
        {/* Popover */}
        {showPopover && (
          <div
            ref={popoverRef}
            className="absolute bottom-16 left-0 w-[95vw] sm:w-[340px] max-w-[340px] rounded-2xl border border-[#30363d] bg-[#161b22]/95 backdrop-blur-xl shadow-2xl p-4 z-50"
          >
            <div className="flex flex-col gap-6">
              <div>
                <h3 className="text-sm font-semibold mb-3">
                  Upload PDFs
                </h3>

                <PdfUploader />
              </div>

              <div>
                <h3 className="text-sm font-semibold mb-3">
                  Add YouTube Context
                </h3>

                <UrlInput />
              </div>
            </div>
          </div>
        )}

        {/* Input Container */}
        <div className="flex items-center gap-2 sm:gap-3 bg-[#1a1d24] border border-[#30363d] rounded-2xl px-2 sm:px-3 py-2 sm:py-3">
          {/* Attachment Button */}
          <button
            onClick={() =>
              setShowPopover(
                !showPopover
              )
            }
            className="w-10 h-10 shrink-0 rounded-xl hover:bg-[#2a2f3a] transition flex items-center justify-center text-xl"
          >
            +
          </button>

          {/* Input */}
          <textarea
          value={input}
          disabled={disabled}
          rows={1}
          onChange={(e) => {
            setInput(e.target.value);

            // auto resize
            e.target.style.height = "auto";
            e.target.style.height =
              e.target.scrollHeight + "px";
          }}
          onKeyDown={(e) => {
            if (
              e.key === "Enter" &&
              !e.shiftKey
            ) {
              e.preventDefault();
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

          {/* Send Button */}
          <button
            onClick={handleSubmit}
            disabled={disabled}
            className="shrink-0 bg-blue-600 hover:bg-blue-700 px-4 sm:px-5 py-2 rounded-xl transition"
          >
            ↑
          </button>
        </div>
      </div>
    </div>
  );
}