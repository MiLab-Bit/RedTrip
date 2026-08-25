import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { AUTH_BASE } from "../../shared/lib/authConfig";

export type AuthUserStatus = "pending" | "active" | "disabled";

/** 与 auth-core 的 PublicUser 对齐（注意不含 email，昵称为空时用占位显示）。 */
export interface AuthUser {
  publicId: string;
  nickname: string | null;
  avatarUrl: string | null;
  status: AuthUserStatus;
  emailVerified: boolean;
  roles: string[];
  createdAt: number;
}

export interface Tokens {
  accessToken: string;
  refreshToken: string;
  expiresIn: number;
  user: AuthUser;
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(AUTH_BASE + path, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
  if (!res.ok) {
    const message =
      (typeof data.message === "string" && data.message) ||
      (typeof data.error === "string" && data.error) ||
      `请求失败 (${res.status})`;
    throw new Error(message);
  }
  return data as T;
}

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  refreshToken: string | null;
  status: "loading" | "authenticated" | "unauthenticated";
  error: string | null;
  bootstrap: () => Promise<void>;
  register: (input: {
    email: string;
    password: string;
    nickname?: string;
  }) => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  /** 用 refreshToken 换取新令牌；失败则清空并返回 false。 */
  refresh: () => Promise<boolean>;
  verifyEmail: (token: string) => Promise<AuthUser>;
  requestPasswordReset: (email: string) => Promise<void>;
  resetPassword: (token: string, newPassword: string) => Promise<void>;
  setError: (e: string | null) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      status: "loading",
      error: null,

      bootstrap: async () => {
        const rt = get().refreshToken;
        if (!rt) {
          set({ status: "unauthenticated" });
          return;
        }
        const ok = await get().refresh();
        if (!ok) set({ status: "unauthenticated" });
      },

      register: async (input) => {
        await api<AuthUser>("/auth/register", {
          method: "POST",
          body: JSON.stringify(input),
        });
        set({ error: null });
      },

      login: async (email, password) => {
        const tokens = await api<Tokens>("/auth/login", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
        set({
          accessToken: tokens.accessToken,
          refreshToken: tokens.refreshToken,
          user: tokens.user,
          status: "authenticated",
          error: null,
        });
      },

      logout: async () => {
        const rt = get().refreshToken;
        try {
          if (rt) {
            await api("/auth/logout", {
              method: "POST",
              body: JSON.stringify({ refreshToken: rt }),
            });
          }
        } catch {
          /* 忽略网络错误，本地状态照清 */
        }
        set({
          user: null,
          accessToken: null,
          refreshToken: null,
          status: "unauthenticated",
          error: null,
        });
      },

      refresh: async () => {
        const rt = get().refreshToken;
        if (!rt) {
          set({ status: "unauthenticated" });
          return false;
        }
        try {
          const tokens = await api<Tokens>("/auth/refresh", {
            method: "POST",
            body: JSON.stringify({ refreshToken: rt }),
          });
          set({
            accessToken: tokens.accessToken,
            refreshToken: tokens.refreshToken,
            user: tokens.user,
            status: "authenticated",
            error: null,
          });
          return true;
        } catch {
          set({
            user: null,
            accessToken: null,
            refreshToken: null,
            status: "unauthenticated",
          });
          return false;
        }
      },

      verifyEmail: async (token) => {
        const user = await api<AuthUser>("/auth/verify-email", {
          method: "POST",
          body: JSON.stringify({ token }),
        });
        set({ user, error: null });
        return user;
      },

      requestPasswordReset: async (email) => {
        await api("/auth/request-password-reset", {
          method: "POST",
          body: JSON.stringify({ email }),
        });
        set({ error: null });
      },

      resetPassword: async (token, newPassword) => {
        await api("/auth/reset-password", {
          method: "POST",
          body: JSON.stringify({ token, newPassword }),
        });
        set({ error: null });
      },

      setError: (e) => set({ error: e }),
    }),
    {
      name: "redtrip:auth",
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({
        user: s.user,
        accessToken: s.accessToken,
        refreshToken: s.refreshToken,
      }),
    },
  ),
);
