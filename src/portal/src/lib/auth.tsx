"use client";

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useRef,
  useCallback,
  ReactNode,
} from "react";
import { useRouter } from "next/navigation";
import { GATEWAY_URL } from "@/lib/api";
import { initAuthFetch } from "@/lib/auth-fetch";

export interface AuthUser {
  userId: string;
  tenantId: string;
  role: "system_admin" | "tenant_admin" | "annotator" | "business_user";
  email: string;
  tenantSlug: string | null;
}

interface AuthContextType {
  user: AuthUser | null;
  getAccessToken: () => string | null;
  setAccessToken: (t: string) => void;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function mapUser(raw: {
  id: string;
  email: string;
  role: string;
  tenant_id: string;
  tenant_slug: string | null;
}): AuthUser {
  return {
    userId: raw.id,
    tenantId: raw.tenant_id,
    role: raw.role as AuthUser["role"],
    email: raw.email,
    tenantSlug: raw.tenant_slug,
  };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const accessTokenRef = useRef<string | null>(null);
  const [user, setUser] = useState<AuthUser | null>(null);
  const router = useRouter();

  const getAccessToken = useCallback(() => accessTokenRef.current, []);
  const setAccessToken = useCallback((t: string) => {
    accessTokenRef.current = t;
  }, []);

  useEffect(() => {
    initAuthFetch(getAccessToken, setAccessToken, (path) => router.replace(path));
  }, [getAccessToken, setAccessToken, router]);

  useEffect(() => {
    fetch(`${GATEWAY_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then(async (res) => {
        if (!res.ok) return;
        const data = await res.json();
        accessTokenRef.current = data.access_token;
        setUser(mapUser(data.user));
      })
      .catch(() => {});
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${GATEWAY_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
      credentials: "include",
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error((body as { error?: { message?: string } }).error?.message ?? "Login failed");
    }

    const data = await res.json();
    accessTokenRef.current = data.access_token;
    setUser(mapUser(data.user));
  }, []);

  const logout = useCallback(async () => {
    await fetch(`${GATEWAY_URL}/api/v1/auth/logout`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(accessTokenRef.current ? { Authorization: `Bearer ${accessTokenRef.current}` } : {}),
      },
      body: JSON.stringify({ access_token: accessTokenRef.current ?? "" }),
      credentials: "include",
    }).catch(() => {});
    accessTokenRef.current = null;
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, getAccessToken, setAccessToken, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
