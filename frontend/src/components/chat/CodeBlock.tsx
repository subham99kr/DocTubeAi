import {
  useState,
  memo,
} from "react";

import {
  Copy,
  Check,
} from "lucide-react";

import {
  Prism as SyntaxHighlighter,
} from "react-syntax-highlighter";

import {
  oneDark,
} from "react-syntax-highlighter/dist/esm/styles/prism";

type Props = {
  language: string;
  code: string;
};

function CodeBlock({
  language,
  code,
}: Props) {
  const [copied, setCopied] =
    useState(false);

  async function handleCopy() {
    await navigator.clipboard.writeText(
      code
    );

    setCopied(true);

    setTimeout(() => {
      setCopied(false);
    }, 1500);
  }

  return (
    <div className="w-full min-w-0 my-4 overflow-hidden rounded-2xl border border-[#30363d] bg-[#0d1117]">
      
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-[#30363d] bg-[#161b22]">
        <span className="text-xs text-gray-400 uppercase tracking-wide truncate">
          {language || "code"}
        </span>

        <button
          onClick={handleCopy}
          className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition shrink-0"
        >
          {copied ? (
            <>
              <Check size={14} />
              Copied
            </>
          ) : (
            <>
              <Copy size={14} />
              Copy code
            </>
          )}
        </button>
      </div>

      {/* Code */}
      <div className="overflow-x-auto">
        <SyntaxHighlighter
          language={language}
          style={oneDark}
          wrapLongLines={false}
          customStyle={{
            margin: 0,
            padding: "16px",
            background:
              "#0d1117",
            fontSize: "14px",
            borderRadius: 0,
          }}
        >
          {code}
        </SyntaxHighlighter>
      </div>
    </div>
  );
}

export default memo(CodeBlock);