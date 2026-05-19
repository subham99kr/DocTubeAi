import {
  memo,
} from "react";

import {
  motion,
} from "framer-motion";

type Props = {
  content: string;
};

function StreamingMessage({
  content,
}: Props) {
  if (!content) {
    return null;
  }

  return (
    <div className="flex justify-start w-full min-w-0">
      <motion.div
        initial={{
          opacity: 0,
          y: 8,
        }}
        animate={{
          opacity: 1,
          y: 0,
        }}
        transition={{
          duration: 0.15,
        }}
        className="relative max-w-[92%] sm:max-w-[85%] lg:max-w-3xl rounded-2xl overflow-hidden border border-white/10 bg-[#161b22]/90"
      >
        {/* subtle glow */}
        <div className="absolute inset-0 bg-gradient-to-r from-blue-500/5 via-cyan-500/5 to-purple-500/5 pointer-events-none" />

        {/* content */}
        <div className="relative z-10 px-4 py-3">
          <div className="whitespace-pre-wrap break-words text-sm leading-7 text-white">
            {content}
          </div>

          {/* blinking cursor */}
          <span className="ml-1 text-cyan-400 animate-pulse"> ▋ </span>
        </div>
      </motion.div>
    </div>
  );
}

export default memo(
  StreamingMessage
);