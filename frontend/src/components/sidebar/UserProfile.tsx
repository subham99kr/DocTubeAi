import { useState } from "react";

import { useAuth } from "../../context/AuthContext";

import LoginButton from "../auth/LoginButton";

export default function UserProfile() {
  const {
    user,
    logout,
    loading,
  } = useAuth();

  const [
    logoutLoading,
    setLogoutLoading,
  ] = useState(false);

  function handleLogout() {
    setLogoutLoading(true);

    setTimeout(() => {
      logout();

      window.location.reload();
    }, 500);
  }

  // AUTH / LOGOUT LOADING
  if (
    loading ||
    logoutLoading
  ) {
    return (
      <div className="bg-[#1a1d24] border border-[#30363d] rounded-2xl p-4 animate-pulse">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-[#2a2f3a]" />

          <div className="flex-1">
            <div className="h-4 w-24 bg-[#2a2f3a] rounded mb-2" />

            <div className="h-3 w-36 bg-[#2a2f3a] rounded" />
          </div>
        </div>

        <div className="mt-4 h-10 rounded-xl bg-[#2a2f3a]" />
      </div>
    );
  }

  const urlParams =
    new URLSearchParams(
      window.location.search
    );

  const hasOAuthCode =
    urlParams.has("code");

  // During OAuth redirect,
  // don't show login button
  if (!user) {
    if (hasOAuthCode) {
      return (
        <div className="bg-[#1a1d24] border border-[#30363d] rounded-2xl p-4 animate-pulse">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-[#2a2f3a]" />

            <div className="flex-1">
              <div className="h-4 w-24 bg-[#2a2f3a] rounded mb-2" />

              <div className="h-3 w-36 bg-[#2a2f3a] rounded" />
            </div>
          </div>

          <div className="mt-4 h-10 rounded-xl bg-[#2a2f3a]" />
        </div>
      );
    }

    return <LoginButton />;
  }

  // LOGGED IN
  return (
    <div className="bg-[#1a1d24] border border-[#30363d] rounded-2xl p-4">
      <div className="flex items-center gap-3">
        {/* Avatar */}
        <div className="w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center font-bold">
          {user.name?.[0] || "U"}
        </div>

        {/* User Info */}
        <div className="flex-1 min-w-0">
          <p className="font-medium truncate">
            {user.name}
          </p>

          <p className="text-xs text-gray-400 truncate">
            {user.email}
          </p>
        </div>
      </div>

      {/* Logout */}
      <button
        onClick={handleLogout}
        className="mt-4 w-full bg-red-600 hover:bg-red-700 py-2 rounded-xl transition"
      >
        Logout
      </button>
    </div>
  );
}