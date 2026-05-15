import { motion } from "framer-motion";

import { useNavigate } from "react-router-dom";

type Session = {
  session_id: string;
  title?: string;
};

type Props = {
  sessions: Session[];

  activeSessionId: string;

  onSelect: (
    sessionId: string
  ) => void;
};

export default function SessionList({
  sessions,
  activeSessionId,
  onSelect,
}: Props) {
  const navigate =
    useNavigate();

  return (
    <div className="flex flex-col gap-2">
      {sessions.map((session) => (
        <motion.button
          key={session.session_id}
          onClick={() => {
            onSelect(
              session.session_id
            );

            navigate(
              `/chats/history/${session.session_id}`
            );
          }}
          whileHover={{
            scale: 1.02,
          }}
          whileTap={{
            scale: 0.98,
          }}
          transition={{
            duration: 0.15,
          }}
          layout
          className={`text-left p-3 rounded-xl border transition-all duration-200 ${
            activeSessionId ===
            session.session_id
              ? "bg-blue-600 border-blue-500 shadow-lg"
              : "bg-[#1a1d24] border-[#30363d] hover:bg-[#22262f]"
          }`}
        >
          <p className="truncate text-sm">
            {session.title
              ? session.title
                  .charAt(0)
                  .toUpperCase() +
                session.title.slice(1)
              : "Untitled Chat"}
          </p>
        </motion.button>
      ))}
    </div>
  );
}