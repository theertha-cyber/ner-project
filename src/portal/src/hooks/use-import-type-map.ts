"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";

/** Each unknown type maps to an existing entity type by name, or to a new one. */
export type TypeMapEntry = { to: string } | { create: true };

export interface TypeMapPayload {
  sourceFile: string;
  mapping: Record<string, TypeMapEntry>;
}

export interface TypeMapResult {
  source_file: string;
  type_map: Record<string, { to: string; created: boolean }>;
  training_eligible: boolean;
}

/**
 * Resolve an imported file's unmapped entity types. Mapping to a new type creates it
 * through the canonical entity-config path with `provenance = 'imported'`; nothing is
 * created implicitly.
 */
export function useImportTypeMap() {
  const qc = useQueryClient();
  return useMutation<TypeMapResult, Error, TypeMapPayload>({
    mutationFn: async ({ sourceFile, mapping }) => {
      const res = await authFetch(
        `/api/v1/annotation-imports/${encodeURIComponent(sourceFile)}/type-map`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(mapping),
        },
      );
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail?.message ?? `Type mapping failed: ${res.status}`);
      }
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["imported-annotations"] });
      qc.invalidateQueries({ queryKey: ["entity-types"] });
    },
  });
}
