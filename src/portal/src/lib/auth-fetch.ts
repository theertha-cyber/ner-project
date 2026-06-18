import { GATEWAY_URL, DOCUMENT_URL, ANNOTATION_URL, TRAINING_URL, EXTRACTION_URL } from "@/lib/api";

let _getToken: () => string | null = () => null;
let _setToken: (t: string) => void = () => {};
let _navigate: (path: string) => void = (path) => {
  window.location.replace(path);
};

export function initAuthFetch(
  getToken: () => string | null,
  setToken: (t: string) => void,
  navigate: (path: string) => void,
): void {
  _getToken = getToken;
  _setToken = setToken;
  _navigate = navigate;
}

let pendingRefresh: Promise<string> | null = null;

function resolveUrl(url: string): string {
  if (/^https?:\/\//.test(url)) return url;
  if (
    url.startsWith("/api/v1/admin") ||
    url.startsWith("/api/v1/auth") ||
    url.startsWith("/api/v1/tenants") ||
    url.startsWith("/api/v1/dashboard") ||
    url.startsWith("/api/v1/entity-type") ||
    url.startsWith("/api/v1/users")
  )
    return `${GATEWAY_URL}${url}`;
  // Span and prelabel endpoints live in the annotation service despite the /documents/ prefix
  if (/^\/api\/v1\/documents\/[^/]+\/(spans|prelabel)/.test(url))
    return `${ANNOTATION_URL}${url}`;
  if (url.startsWith("/api/v1/annotation")) return `${ANNOTATION_URL}${url}`;
  if (url.startsWith("/api/v1/document")) return `${DOCUMENT_URL}${url}`;
  if (url.startsWith("/api/v1/training") || url.startsWith("/api/v1/models"))
    return `${TRAINING_URL}${url}`;
  if (url.startsWith("/api/v1/extraction")) return `${EXTRACTION_URL}${url}`;
  return url;
}

export async function authFetch(url: string, init: RequestInit = {}): Promise<Response> {
  const fullUrl = resolveUrl(url);
  const headers = new Headers(init.headers);
  const token = _getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(fullUrl, { ...init, headers, credentials: "include" });
  if (res.status !== 401) return res;

  if (!pendingRefresh) {
    pendingRefresh = fetch(`${GATEWAY_URL}/api/v1/auth/refresh`, {
      method: "POST",
      credentials: "include",
    })
      .then(async (r) => {
        if (!r.ok) throw new Error("Refresh failed");
        const data = await r.json();
        _setToken(data.access_token);
        return data.access_token as string;
      })
      .finally(() => {
        pendingRefresh = null;
      });
  }

  let newToken: string;
  try {
    newToken = await pendingRefresh;
  } catch {
    _navigate("/login");
    throw new Error("Session expired");
  }

  const retryHeaders = new Headers(init.headers);
  retryHeaders.set("Authorization", `Bearer ${newToken}`);
  const retried = await fetch(fullUrl, {
    ...init,
    headers: retryHeaders,
    credentials: "include",
  });

  if (retried.status === 401) {
    _navigate("/login");
    throw new Error("Session expired");
  }

  return retried;
}
