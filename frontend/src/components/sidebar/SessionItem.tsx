type Props = {
  title: string;
  active?: boolean;
  onClick: () => void;
};

export default function SessionItem({
  title,
  active,
  onClick,
}: Props) {
  return (
    <button
      onClick={onClick}
      className={`w-full text-left p-3 rounded-xl border transition ${
        active
          ? "bg-blue-600 border-blue-500"
          : "bg-[#1a1d24] border-[#30363d] hover:bg-[#222733]"
      }`}
    >
      <p className="truncate text-sm">
        {title}
      </p>
    </button>
  );
}