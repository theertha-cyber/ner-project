import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";

export interface AuditEvent {
  id: string;
  actor: string;
  role: string;
  action: string;
  target: string;
  kind: string;
  tenant_id: string | null;
  created_at: string;
}

export interface AuditLogResponse {
  events: AuditEvent[];
  total: number;
  page: number;
  per_page: number;
}

export function useAuditLog(page: number, perPage: number = 50) {
  const params = new URLSearchParams();
  params.set("page", String(page));
  params.set("per_page", String(perPage));
  const qs = params.toString();

  return useQuery<AuditLogResponse>({
    queryKey: ["audit-log", { page, perPage }],
    queryFn: async () => {
      const res = await authFetch(`/api/v1/admin/audit-log?${qs}`);
      if (!res.ok) throw new Error(`Failed to fetch audit log: ${res.status}`);
      return res.json();
    },
    placeholderData: (prev) => prev,
  });
}
