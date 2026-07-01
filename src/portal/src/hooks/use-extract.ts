"use client";

import { useState, useCallback } from "react";
import { authFetch } from "@/lib/auth-fetch";
import type { ExtractedEntity, ExtractResponse } from "@/types/extraction";

export function useExtract() {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<ExtractedEntity[] | null>(null);
  const [modelVersion, setModelVersion] = useState<string | null>(null);

  const run = useCallback(async (text: string) => {
    if (!text.trim()) return;
    setRunning(true);
    setResult(null);
    try {
      const res = await authFetch("/api/v1/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) throw new Error(`Extraction failed: ${res.status}`);
      const data: ExtractResponse = await res.json();
      setResult(data.entities);
      if (data.model_version != null) setModelVersion(data.model_version);
    } finally {
      setRunning(false);
    }
  }, []);

  return { running, result, modelVersion, run };
}
