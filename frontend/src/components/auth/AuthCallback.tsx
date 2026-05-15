import { useEffect } from "react";

import { useNavigate } from "react-router-dom";

import { exchangeCodeForToken } from "../../api/authApi";

import { useAuth } from "../../context/AuthContext";

export default function AuthCallback() {
  const navigate = useNavigate();

  const { login } = useAuth();

  useEffect(() => {
    handleAuth();
  }, []);

  async function handleAuth() {
    try {
      const params =
        new URLSearchParams(
          window.location.search
        );

      const code = params.get("code");

      if (!code) {
        return;
      }

      const data =
        await exchangeCodeForToken(code);

      login(
        data.access_token,
        data.user
      );

      navigate("/");
    } catch (error) {
      console.error(error);
    }
  }

  return (
    <div className="h-screen flex items-center justify-center bg-[#0e1117] text-white">
      <p>Authenticating...</p>
    </div>
  );
}