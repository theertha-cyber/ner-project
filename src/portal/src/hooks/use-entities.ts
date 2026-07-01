"use client";

import { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/auth-fetch";
import type { EntityItem, EntityListResponse } from "@/types/extraction";

export type ReviewFilter = "all" | "unreviewed" | "confirmed" | "corrected" | "rejected";

export function useEntities(filter: ReviewFilter = "all") {
  const [entities, setEntities] = useState<EntityItem[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);

  const fetchEntities = useCallback(async (f: ReviewFilter) => {
    setIsLoading(true);
    try {
      const url =
        f === "all" ? "/api/v1/entities" : `/api/v1/entities?reviewStatus=${f}`;
      const res = await authFetch(url);
      if (!res.ok) throw new Error(`Failed to fetch entities: ${res.status}`);
      const data: EntityListResponse = await res.json();
      setEntities(data.items);
      setTotal(data.total);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEntities(filter);
  }, [filter, fetchEntities]);

  const confirm = useCallback(async (id: string) => {
    setEntities((prev) =>
      prev.map((e) => (e.id === id ? { ...e, review_status: "confirmed" } : e))
    );
    await authFetch(`/api/v1/entities/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ review_status: "confirmed" }),
    });
  }, []);

  const reject = useCallback(async (id: string) => {
    setEntities((prev) =>
      prev.map((e) => (e.id === id ? { ...e, review_status: "rejected" } : e))
    );
    await authFetch(`/api/v1/entities/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ review_status: "rejected" }),
    });
  }, []);

  return { entities, total, isLoading, confirm, reject };
}
