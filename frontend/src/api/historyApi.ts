const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL;

export async function loadHistory(
  sessionId: string,
  token?: string
) {
  const response = await fetch(
    `${BACKEND_URL}/chats/history/${sessionId}`,
    {
      headers: {
        ...(token
          ? {
              Authorization: `Bearer ${token}`,
            }
          : {}),
      },
    }
  );

  if (!response.ok) {
    throw new Error(
      "Failed to load chat history"
    );
  }

  return response.json();
}