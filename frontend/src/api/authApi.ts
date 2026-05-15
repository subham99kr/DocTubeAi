const BACKEND_URL =
  import.meta.env.VITE_BACKEND_URL;

const PUBLIC_BACKEND_URL =
  import.meta.env.VITE_PUBLIC_BACKEND_URL;

export function getGoogleLoginUrl() {
  return `${PUBLIC_BACKEND_URL}/login/google`;
}

export async function exchangeCodeForToken(
  code: string
) {
  const response = await fetch(
    `${PUBLIC_BACKEND_URL}/auth/callback?code=${code}`,
    {
      method: "GET",
    }
  );

  if (!response.ok) {
    throw new Error(
      "Failed to authenticate user"
    );
  }

  return response.json();
}

export async function validateToken(
  token: string
) {
  const response = await fetch(
    `${BACKEND_URL}/auth/me`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  if (!response.ok) {
    throw new Error("Invalid token");
  }

  return response.json();
}