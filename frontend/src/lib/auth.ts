import { User } from "@/types/session";

const TOKEN_KEY = "access_token";
const USER_KEY = "user";

export const auth = {
  /** Save token and user profile to localStorage */
  setSession(token: string, user: User) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },

  /** Get stored access token */
  getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem(TOKEN_KEY);
  },

  /** Get stored user profile */
  getUser(): User | null {
    if (typeof window === "undefined") return null;
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as User;
    } catch {
      return null;
    }
  },

  /** Check if the user is authenticated */
  isAuthenticated(): boolean {
    return !!this.getToken();
  },

  /** Clear auth data from localStorage */
  clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },
};
