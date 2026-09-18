"use client";

import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";

export interface ImportFile {
  source_file: string;
  row_count: number;
  type_map: Record<string, { to: string; created: boolean }>;
  training_eligible: boolean;
  training_eligible_at: string | null;
  pending_count: number;
  reviewed_count: number;
  unmapped_types: { type: string; row_count: number }[];
}

/** One row per imported file: size, rows still needing a type mapping, and whether the
 * file is training-eligible. */
export function useImportFiles(enabled = true) {
  return useQuery<{ files: ImportFile[] }>({
    queryKey: ["import-files"],
    enabled,
    queryFn: async () => {
      const res = await authFetch("/api/v1/annotation-imports");
      if (!res.ok) throw new Error(`Failed to load imported files: ${res.status}`);
      return res.json();
    },
  });
}
