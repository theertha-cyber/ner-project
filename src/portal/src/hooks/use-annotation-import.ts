import { useState } from "react";
import { authFetch } from "@/lib/auth-fetch";

export interface ImportResult {
  imported_count: number;
  skipped_count: number;
  warnings: { row_index: number; message: string }[];
  entity_type_counts: Record<string, number>;
}

export type ImportState =
  | { status: "idle" }
  | { status: "uploading" }
  | { status: "success"; result: ImportResult }
  | { status: "error"; error: string };

export function useAnnotationImport() {
  const [state, setState] = useState<ImportState>({ status: "idle" });

  const importAnnotations = async (file: File): Promise<void> => {
    setState({ status: "uploading" });

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await authFetch("/api/v1/annotation-import", {
        method: "POST",
        body: formData,
      });

      if (res.status === 413) {
        const err = await res.json().catch(() => ({ detail: { message: "File exceeds the 50MB maximum" } }));
        setState({ status: "error", error: err.detail?.message ?? "File exceeds the 50MB maximum" });
        return;
      }

      if (res.status === 415) {
        const err = await res.json().catch(() => ({ detail: { message: "Unsupported file type" } }));
        setState({ status: "error", error: err.detail?.message ?? "Unsupported file type" });
        return;
      }

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setState({
          status: "error",
          error: (err as { detail?: { message?: string } }).detail?.message ?? "Import failed",
        });
        return;
      }

      const data = (await res.json()) as ImportResult;
      setState({ status: "success", result: data });
    } catch {
      setState({ status: "error", error: "Network error. Please try again." });
    }
  };

  const reset = () => setState({ status: "idle" });

  return { state, importAnnotations, reset };
}
