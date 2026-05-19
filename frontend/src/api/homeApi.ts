const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL;

export async function loadHome(
  token?: string
) {
  const response = await fetch(
    `${BACKEND_URL}/home_init`,
    {
      method: "GET",

      headers: {
        "Content-Type":
          "application/json",

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
      "Failed to load home sessions"
    );
  }

  return response.json();
}
