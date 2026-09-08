"use client";

import { useCallback } from "react";
import { authFetch } from "@/lib/auth-fetch";

/**
 * Fires change 1's per-document LLM pre-labeling endpoint for a single document.
 *
 * Deliberately one document per call: the caller loops sequentially over a batch rather than
 * this hook fanning out, so there is exactly one concurrency model in the upload flow and one
 * failure surface per document.
 *
 * Routed through `authFetch` (ADR-001) so the gateway sees the same tenant context as every
 * other portal request — never a raw `fetch`, and never a tenant id carried in UI state.
 */
export function usePrelabelTrigger() {
  const trigger = useCallback(async (docId: string): Promise<void> => {
    const res = await authFetch(`/api/v1/documents/${docId}/prelabel/llm`, {
      method: "POST",
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      const detail = body?.detail;
      const message =
        typeof detail === "string"
          ? detail
          : (detail?.message ?? `Pre-labeling request failed: ${res.status}`);
      throw new Error(message);
    }
  }, []);

  return { trigger };
}
