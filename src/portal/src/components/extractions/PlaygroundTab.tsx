"use client";

import { useState } from "react";
import { useExtract } from "@/hooks/use-extract";
import { Spinner } from "@/components/ui";

const SAMPLE_TEXT =
  "Apple Inc. was founded by Steve Jobs and Steve Wozniak in Cupertino, California. The company is headquartered in San Francisco.";

const ENTITY_COLORS: Record<string, string> = {
  "B-PER": "#6366f1",
  "I-PER": "#6366f1",
  "B-ORG": "#f59e0b",
  "I-ORG": "#f59e0b",
  "B-LOC": "#10b981",
  "I-LOC": "#10b981",
  "B-MISC": "#8b5cf6",
  "I-MISC": "#8b5cf6",
};

function entityColor(type: string): string {
  return ENTITY_COLORS[type] ?? "#94a3b8";
}

export function PlaygroundTab() {
  const [text, setText] = useState(SAMPLE_TEXT);
  const { running, result, modelVersion, run } = useExtract();

  const versionLabel = modelVersion ? `model v${modelVersion} · serving` : "— · serving";

  return (
    <div
      style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 18 }}
    >
      {/* Left card: input */}
      <div
        className="rounded-xl border border-border bg-surface-raised p-5 flex flex-col gap-3"
        style={{ boxShadow: "var(--shadow-card)" }}
      >
        <div className="flex items-baseline justify-between gap-2">
          <h2 className="text-sm font-semibold text-text-primary">Input text</h2>
          <span className="font-mono text-xs text-text-secondary">{versionLabel}</span>
        </div>

        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          rows={10}
          className="w-full resize-y rounded-lg border border-border bg-surface p-3 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-brand-primary"
          placeholder="Enter text to extract entities from…"
        />

        <button
          type="button"
          disabled={running || !text.trim()}
          onClick={() => run(text)}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white transition-opacity hover:bg-brand-hover disabled:opacity-50"
        >
          {running && <Spinner size="sm" />}
          Run extraction
        </button>

        <p className="text-xs text-text-secondary">
          Whitespace-tokenized · POST /internal/v1/infer · mapped to char offsets. Not persisted.
        </p>
      </div>

      {/* Right card: results */}
      <div
        className="rounded-xl border border-border bg-surface-raised p-5 flex flex-col gap-3"
        style={{ boxShadow: "var(--shadow-card)" }}
      >
        <div className="flex items-baseline justify-between gap-2">
          <h2 className="text-sm font-semibold text-text-primary">Entities</h2>
          {result && (
            <span className="text-xs text-text-secondary">
              {result.length} found · sorted by confidence
            </span>
          )}
        </div>

        {running ? (
          <div className="flex flex-1 items-center justify-center py-16">
            <Spinner size="md" />
          </div>
        ) : result === null ? (
          <p className="py-8 text-center text-sm text-text-secondary">
            Run an extraction to see results.
          </p>
        ) : result.length === 0 ? (
          <p className="py-8 text-center text-sm text-text-secondary">No entities found.</p>
        ) : (
          <div className="flex flex-col divide-y divide-border">
            {result.map((entity, i) => (
              <div key={i} className="flex items-center gap-3 py-2.5">
                <span className="flex items-center gap-1.5 font-mono text-xs">
                  <span
                    className="inline-block h-2 w-2 rounded-full flex-shrink-0"
                    style={{ background: entityColor(entity.entity_type) }}
                  />
                  {entity.entity_type}
                </span>
                <span className="flex-1 text-sm font-semibold text-text-primary truncate">
                  {entity.value}
                </span>
                <span className="ml-auto text-xs text-text-secondary tabular-nums">
                  {entity.confidence.toFixed(3)}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
