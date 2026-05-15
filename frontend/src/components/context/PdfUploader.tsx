import { useRef } from "react";

import { uploadPdfs } from "../../api/uploadApi";

import { useChat } from "../../context/ChatContext";

import { useAuth } from "../../context/AuthContext";

export default function PdfUploader() {
  const inputRef =
    useRef<HTMLInputElement | null>(null);

  const {
    sessionId,
    uploadedPdfs,
    setUploadedPdfs,
  } = useChat();

  const { token } = useAuth();

  async function handleUpload(
    e: React.ChangeEvent<HTMLInputElement>
  ) {
    const files = e.target.files;

    if (!files || files.length === 0) {
      return;
    }

    try {
      const response = await uploadPdfs(
        Array.from(files),
        sessionId,
        token || undefined
      );

      const filenames =
        response.filenames || [];

      setUploadedPdfs([
        ...uploadedPdfs,
        ...filenames,
      ]);

      if (inputRef.current) {
        inputRef.current.value = "";
      }
    } catch (error) {
      console.error(error);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <input
        ref={inputRef}
        type="file"
        multiple
        accept=".pdf"
        onChange={handleUpload}
        className="text-sm"
      />

      <div className="flex flex-col gap-2">
        {uploadedPdfs.map((pdf, index) => (
          <div
            key={index}
            className="bg-[#1a1d24] border border-[#30363d] rounded-lg px-3 py-2 text-sm"
          >
            {pdf}
          </div>
        ))}
      </div>
    </div>
  );
}