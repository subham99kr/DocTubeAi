import { uploadPdfs } from "../api/uploadApi";

import { uploadYoutubeTranscript } from "../api/uploadApi";

import { useAuth } from "../context/AuthContext";

import { useChat } from "../context/ChatContext";

export function useUploads() {
  const { token } = useAuth();

  const {
    sessionId,
    uploadedPdfs,
    setUploadedPdfs,
    urls,
    setUrls,
  } = useChat();

  async function uploadPdfFiles(
    files: File[]
  ) {
    try {
      const response =
        await uploadPdfs(
          files,
          sessionId,
          token || undefined
        );

      const filenames =
        response.filenames || [];

      setUploadedPdfs([
        ...uploadedPdfs,
        ...filenames,
      ]);
    } catch (error) {
      console.error(error);
    }
  }

  async function uploadYoutubeUrl(
    url: string
  ) {
    try {
      const response =
        await uploadYoutubeTranscript(
          url,
          sessionId,
          token || undefined
        );

      setUrls([
        ...urls,
        response.title,
      ]);
    } catch (error) {
      console.error(error);
    }
  }

  return {
    uploadPdfFiles,
    uploadYoutubeUrl,
  };
}