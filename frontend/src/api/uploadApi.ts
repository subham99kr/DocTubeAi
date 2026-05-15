const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL;

export async function uploadPdfs(
  files: File[],
  sessionId: string,
  token?: string
) {
  const formData = new FormData();

  files.forEach((file) => {
    formData.append("files", file);
  });

  formData.append("session_id", sessionId);

  const response = await fetch(
    `${BACKEND_URL}/uploads/pdfs`,
    {
      method: "POST",

      headers: {
        ...(token
          ? {
              Authorization: `Bearer ${token}`,
            }
          : {}),
      },

      body: formData,
    }
  );

  if (!response.ok) {
    throw new Error("PDF upload failed");
  }

  return response.json();
}

export async function uploadYoutubeTranscript(
  url: string,
  sessionId: string,
  token?: string
) {
  const response = await fetch(
    `${BACKEND_URL}/transcripts/load`,
    {
      method: "POST",

      headers: {
        "Content-Type": "application/json",

        ...(token
          ? {
              Authorization: `Bearer ${token}`,
            }
          : {}),
      },

      body: JSON.stringify({
        url,
        session_id: sessionId,
      }),
    }
  );

  if (!response.ok) {
    throw new Error("Transcript load failed");
  }

  return response.json();
}