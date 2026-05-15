import { useState } from "react";

import { uploadYoutubeTranscript } from "../../api/uploadApi";

import { useChat } from "../../context/ChatContext";

import { useAuth } from "../../context/AuthContext";

const YOUTUBE_REGEX =
  /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.be)\/.+$/;

export default function UrlInput() {
  const [url, setUrl] = useState("");

  const { sessionId, urls, setUrls } =
    useChat();

  const { token } = useAuth();

  async function handleSubmit() {
    if (!url.trim()) return;

    if (!YOUTUBE_REGEX.test(url)) {
      alert("Invalid YouTube URL");
      return;
    }

    try {
      const response =
        await uploadYoutubeTranscript(
          url,
          sessionId,
          token || undefined
        );

      setUrls([
        ...urls,
        response.title || "YouTube Video",
      ]);

      setUrl("");
    } catch (error) {
      console.error(error);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2">
        <input
          type="text"
          value={url}
          onChange={(e) =>
            setUrl(e.target.value)
          }
          placeholder="Paste YouTube URL..."
          className="flex-1 bg-[#1a1d24] border border-[#30363d] rounded-xl px-4 py-3 outline-none"
        />

        <button
          onClick={handleSubmit}
          className="bg-blue-600 hover:bg-blue-700 px-4 rounded-xl"
        >
          Add
        </button>
      </div>

      <div className="flex flex-col gap-2">
        {urls.map((item, index) => (
          <div
            key={index}
            className="bg-[#1a1d24] border border-[#30363d] rounded-lg px-3 py-2 text-sm"
          >
            {item}
          </div>
        ))}
      </div>
    </div>
  );
}