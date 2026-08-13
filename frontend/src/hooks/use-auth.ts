"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { auth } from "@/lib/auth";
import { User } from "@/types/session";

interface AuthState {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

export function useAuth() {
  const router = useRouter();
  const [state, setState] = useState<AuthState>({
    user: null,
    isLoading: true,
    isAuthenticated: false,
  });

  // On mount: load user from localStorage
  useEffect(() => {
    const storedUser = auth.getUser();
    const token = auth.getToken();
    setState({
      user: storedUser,
      isLoading: false,
      isAuthenticated: !!(storedUser && token),
    });
  }, []);

  const login = useCallback(
    async (email: string, password: string) => {
      const response = await api.post("/auth/login", { email, password });
      const { access_token, user } = response.data;
      auth.setSession(access_token, user);
      setState({ user, isLoading: false, isAuthenticated: true });
      router.push("/dashboard");
    },
    [router]
  );

  const register = useCallback(
    async (email: string, password: string, full_name?: string) => {
      const response = await api.post("/auth/register", {
        email,
        password,
        full_name,
      });
      const { access_token, user } = response.data;
      auth.setSession(access_token, user);
      setState({ user, isLoading: false, isAuthenticated: true });
      router.push("/dashboard");
    },
    [router]
  );

  const logout = useCallback(() => {
    auth.clearSession();
    setState({ user: null, isLoading: false, isAuthenticated: false });
    router.push("/login");
  }, [router]);

  return {
    user: state.user,
    isLoading: state.isLoading,
    isAuthenticated: state.isAuthenticated,
    login,
    register,
    logout,
  };
}
