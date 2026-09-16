"use client";

import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import { useAuth } from "@/lib/auth";
import type { TrainingReadiness } from "@/types/seed-bootstrap";

/**
 * Per-entity-type readiness against the platform's per-type threshold.
 *
 * Advisory. Nothing that consumes this may disable or block training submission on it: the
 * enforcement knob is `NER_MIN_ENTITIES_PER_TYPE` server-side, and the decision to train belongs
 * to the System Admin at approval time (ADR-009, ADR-010). What it is for is telling a tenant
 * which labels are starved *before* a GPU run rather than after one.
 */
export function useTrainingReadiness(enabled = true) {
  const { user } = useAuth();
  const tenantSlug = user?.tenantSlug ?? "";

  return useQuery<TrainingReadiness>({
    queryKey: ["training-readiness", tenantSlug],
    enabled: enabled && !!tenantSlug,
    queryFn: async () => {
      const res = await authFetch(`/api/v1/tenants/${tenantSlug}/training-readiness`);
      if (!res.ok) throw new Error(`Failed to fetch readiness: ${res.status}`);
      return res.json();
    },
  });
}
