"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";

export interface AppNotification {
  id: string;
  kind: string;
  title: string;
  body: string | null;
  resource_type: string | null;
  resource_id: string | null;
  read_at: string | null;
  created_at: string;
}

export interface NotificationList {
  items: AppNotification[];
  unread: number;
}

export function useNotifications() {
  return useQuery<NotificationList>({
    queryKey: ["notifications"],
    queryFn: async () => {
      const res = await authFetch("/api/v1/notifications?limit=30");
      if (!res.ok) throw new Error(`Failed to load notifications: ${res.status}`);
      return res.json();
    },
    refetchInterval: 60_000,
  });
}

export function useMarkNotificationRead() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string | "all") => {
      const path = id === "all" ? "/api/v1/notifications/read-all" : `/api/v1/notifications/${id}/read`;
      const res = await authFetch(path, { method: "POST" });
      if (!res.ok && res.status !== 404) throw new Error(`Failed to mark read: ${res.status}`);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["notifications"] }),
  });
}
