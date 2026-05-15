type Props = {
  status?: string;
};

export default function TypingStatus({
  status,
}: Props) {
  if (!status) return null;

  return (
    <div className="px-4 py-2">
      <div className="inline-flex items-center gap-2 text-sm text-gray-400">
        <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />

        <span>{status}</span>
      </div>
    </div>
  );
}