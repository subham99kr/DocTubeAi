import { getGoogleLoginUrl } from "../../api/authApi";

export default function LoginButton() {
  function handleLogin() {
    window.location.href =
      getGoogleLoginUrl();
  }

  return (
    <button
      onClick={handleLogin}
      className="w-full flex items-center justify-center gap-3 bg-white text-black py-3 rounded-xl font-medium hover:bg-gray-200 transition"
    >
      <img
        src="https://www.gstatic.com/firebasejs/ui/2.0.0/images/auth/google.svg"
        alt="google"
        className="w-5 h-5"
      />

      Continue with Google
    </button>
  );
}