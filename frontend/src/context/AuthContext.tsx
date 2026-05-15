import {
  createContext,
  useContext,
  useEffect,
  useState,
} from "react";

import type { ReactNode } from "react";

type User = {
  name: string;
  email?: string;
};

type AuthContextType = {
  token: string | null;

  user: User | null;

  loading: boolean;

  login: (
    token: string,
    user: User
  ) => void;

  logout: () => void;
};

const AuthContext =
  createContext<AuthContextType | null>(
    null
  );

type Props = {
  children: ReactNode;
};

export function AuthProvider({
  children,
}: Props) {
  const [token, setToken] =
    useState<string | null>(null);

  const [user, setUser] =
    useState<User | null>(null);

  const [loading, setLoading] =
    useState(true);

  useEffect(() => {
    const storedToken =
      localStorage.getItem(
        "access_token"
      );

    const storedUser =
      localStorage.getItem("user");

    if (storedToken) {
      setToken(storedToken);
    }

    if (storedUser) {
      setUser(
        JSON.parse(storedUser)
      );
    }

    setLoading(false);
  }, []);

  const login = (
    newToken: string,
    newUser: User
  ) => {
    setToken(newToken);

    setUser(newUser);

    localStorage.setItem(
      "access_token",
      newToken
    );

    localStorage.setItem(
      "user",
      JSON.stringify(newUser)
    );
  };

  const logout = () => {
    setToken(null);

    setUser(null);

    localStorage.removeItem(
      "access_token"
    );

    localStorage.removeItem(
      "user"
    );

    // IMPORTANT
    sessionStorage.removeItem(
      "auth_processed"
    );
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        loading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context =
    useContext(AuthContext);

  if (!context) {
    throw new Error(
      "useAuth must be used inside AuthProvider"
    );
  }

  return context;
}