import {
  memo,
} from "react";

import ReactMarkdown from "react-markdown";

import CodeBlock from "./CodeBlock";

type Props = {
  content: string;
};

function MarkdownRenderer({
  content,
}: Props) {
  return (
    <div className="prose prose-invert max-w-none text-sm overflow-x-auto">
      <ReactMarkdown
        components={{
          code({
            className,
            children,
          }: any) {
            const match =
              /language-(\w+)/.exec(
                className || ""
              );

            const codeString =
              Array.isArray(
                children
              )
                ? children.join("")
                : String(
                    children
                  );

            // BLOCK CODE
            if (match) {
              return (
                <CodeBlock
                  language={
                    match[1]
                  }
                  code={codeString.replace(
                    /\n$/,
                    ""
                  )}
                />
              );
            }

            // INLINE CODE
            return (
              <code className="bg-black/30 px-1.5 py-0.5 rounded text-cyan-300">
                {children}
              </code>
            );
          },

          p({
            children,
          }) {
            return (
              <p className="leading-7 mb-3">
                {children}
              </p>
            );
          },

          ul({
            children,
          }) {
            return (
              <ul className="list-disc pl-5 mb-3">
                {children}
              </ul>
            );
          },

          ol({
            children,
          }) {
            return (
              <ol className="list-decimal pl-5 mb-3">
                {children}
              </ol>
            );
          },

          li({
            children,
          }) {
            return (
              <li className="mb-1">
                {children}
              </li>
            );
          },

          h1({
            children,
          }) {
            return (
              <h1 className="text-2xl font-bold mb-4">
                {children}
              </h1>
            );
          },

          h2({
            children,
          }) {
            return (
              <h2 className="text-xl font-semibold mb-3">
                {children}
              </h2>
            );
          },

          h3({
            children,
          }) {
            return (
              <h3 className="text-lg font-semibold mb-2">
                {children}
              </h3>
            );
          },

          blockquote({
            children,
          }) {
            return (
              <blockquote className="border-l-4 border-cyan-500/40 pl-4 italic text-gray-300 my-3">
                {children}
              </blockquote>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

export default memo(
  MarkdownRenderer
);