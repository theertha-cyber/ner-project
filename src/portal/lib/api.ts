const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
}

function getTokens(): { access: string | null; refresh: string | null } {
  if (typeof window === "undefined") return { access: null, refresh: null };
  return {
    access: localStorage.getItem("access_token"),
    refresh: localStorage.getItem("refresh_token"),
  };
}

function setTokens(access: string, refresh: string) {
  localStorage.setItem("access_token", access);
  localStorage.setItem("refresh_token", refresh);
}

function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

export { getTokens, setTokens, clearTokens };

async function refreshAccessToken(): Promise<string | null> {
  const { refresh } = getTokens();
  if (!refresh) return null;

  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    });
    if (!res.ok) {
      clearTokens();
      return null;
    }
    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    return data.access_token;
  } catch {
    clearTokens();
    return null;
  }
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const { access } = getTokens();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(access ? { Authorization: `Bearer ${access}` } : {}),
    ...options.headers,
  };

  const doFetch = async (token: string | null) => {
    const res = await fetch(`${API_BASE}${path}`, {
      method: options.method || "GET",
      headers: token
        ? { ...headers, Authorization: `Bearer ${token}` }
        : headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });

    if (res.status === 401 && access) {
      const newToken = await refreshAccessToken();
      if (newToken) {
        return doFetch(newToken);
      }
      if (typeof window !== "undefined") {
        window.location.href = "/login";
      }
      throw new Error("Session expired");
    }

    if (!res.ok) {
      const error = await res.json().catch(() => ({ error: { message: "Request failed" } }));
      throw new Error(error.error?.message || `HTTP ${res.status}`);
    }

    return res.json() as Promise<T>;
  };

  return doFetch(access);
}
