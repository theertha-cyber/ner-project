"use client";

import { useState, useCallback } from "react";
import { authFetch } from "@/lib/auth-fetch";
import type { ExtractedEntity, ExtractResponse } from "@/types/extraction";

function cleanEntityType(label: string): string {
  return label.replace(/^[BI]-/, "");
}

export function mergeBIOEntities(entities: ExtractedEntity[]): ExtractedEntity[] {
  if (entities.length === 0) return [];

  const sorted = [...entities].sort((a, b) => a.start_offset - b.start_offset);
  const merged: ExtractedEntity[] = [];
  let current: ExtractedEntity | null = null;
  let currentConfidences: number[] = [];

  for (const entity of sorted) {
    const isContinuation = entity.entity_type.startsWith("I-");
    const baseType = cleanEntityType(entity.entity_type);

    if (
      current &&
      isContinuation &&
      cleanEntityType(current.entity_type) === baseType &&
      entity.start_offset <= current.end_offset + 1
    ) {
      current.value += " " + entity.value;
      current.end_offset = entity.end_offset;
      current.entity_type = baseType;
      currentConfidences.push(entity.confidence);
      current.confidence = currentConfidences.reduce((a, b) => a + b, 0) / currentConfidences.length;
    } else {
      if (current) {
        current.entity_type = cleanEntityType(current.entity_type);
        merged.push(current);
      }
      current = { ...entity };
      current.entity_type = baseType;
      currentConfidences = [entity.confidence];
    }
  }

  if (current) {
    current.entity_type = cleanEntityType(current.entity_type);
    merged.push(current);
  }

  return merged;
}

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
      setResult(mergeBIOEntities(data.entities));
      if (data.model_version != null) setModelVersion(data.model_version);
    } finally {
      setRunning(false);
    }
  }, []);

  return { running, result, modelVersion, run };
}
