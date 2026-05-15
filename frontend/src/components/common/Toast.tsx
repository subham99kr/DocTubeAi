type Props = {
  message: string;
  type?: "success" | "error";
};

export default function Toast({
  message,
  type = "success",
}: Props) {
  return (
    <div
      className={`fixed bottom-6 right-6 px-5 py-3 rounded-xl shadow-lg border z-50 ${
        type === "success"
          ? "bg-green-600 border-green-500"
          : "bg-red-600 border-red-500"
      }`}
    >
      {message}
    </div>
  );
}