"use client";

import { useState, useMemo } from "react";
import { useExtract } from "@/hooks/use-extract";
import { useModelVersions } from "@/hooks/use-model-versions";
import { Spinner } from "@/components/ui";
import { BaseModelConfirmDialog } from "./BaseModelConfirmDialog";
import type { ExtractedEntity } from "@/types/extraction";

const SAMPLE_TEXT =
  "Apple Inc. was founded by Steve Jobs and Steve Wozniak in Cupertino, California. The company is headquartered in San Francisco.";

const ENTITY_COLORS: Record<string, string> = {
  PER: "#6366f1",
  ORG: "#f59e0b",
  LOC: "#10b981",
  MISC: "#8b5cf6",
};

function entityColor(type: string): string {
  return ENTITY_COLORS[type] ?? "#94a3b8";
}

function groupEntities(entities: ExtractedEntity[]): Map<string, ExtractedEntity[]> {
  const groups = new Map<string, ExtractedEntity[]>();
  for (const entity of entities) {
    const type = entity.entity_type;
    if (!groups.has(type)) groups.set(type, []);
    groups.get(type)!.push(entity);
  }
  for (const [, items] of groups) {
    items.sort((a, b) => a.start_offset - b.start_offset);
  }
  return groups;
}

export function PlaygroundTab() {
  const [text, setText] = useState(SAMPLE_TEXT);
  const [showBaseModelConfirm, setShowBaseModelConfirm] = useState(false);
  const { running, result, modelVersion, run } = useExtract();
  const { activeModel } = useModelVersions();

  const versionLabel = modelVersion ? `model v${modelVersion} · serving` : "— · serving";

  function handleRunClick() {
    if (activeModel?.version_number === 0) {
      setShowBaseModelConfirm(true);
      return;
    }
    run(text);
  }

  const groups = useMemo(() => result ? groupEntities(result) : null, [result]);
  const sortedTypeKeys = useMemo(
    () => groups ? [...groups.keys()].sort((a, b) => a.localeCompare(b)) : null,
    [groups]
  );
  const entityCount = result?.length ?? 0;
  const typeCount = groups?.size ?? 0;

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
          onClick={handleRunClick}
          className="flex w-full items-center justify-center gap-2 rounded-lg bg-brand-primary px-4 py-2 text-sm font-semibold text-white transition-opacity hover:bg-brand-hover disabled:opacity-50"
        >
          {running && <Spinner size="sm" />}
          Run extraction
        </button>

        {showBaseModelConfirm && (
          <BaseModelConfirmDialog
            onConfirm={() => {
              setShowBaseModelConfirm(false);
              run(text);
            }}
            onCancel={() => setShowBaseModelConfirm(false)}
          />
        )}

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
              {entityCount} entities · {typeCount} types
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
        ) : entityCount === 0 ? (
          <p className="py-8 text-center text-sm text-text-secondary">No entities found.</p>
        ) : (
          <div className="flex flex-col gap-5">
            {sortedTypeKeys!.map((type) => {
              const items = groups!.get(type)!;
              return (
                <div key={type}>
                  <div className="flex items-center gap-2 mb-2">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full flex-shrink-0"
                      style={{ background: entityColor(type) }}
                    />
                    <span className="text-xs font-semibold text-text-primary tracking-wider uppercase">
                      {type}
                    </span>
                    <span className="text-[10px] text-text-secondary font-mono">
                      {items.length}
                    </span>
                  </div>
                  <div className="flex flex-col divide-y divide-border rounded-lg border border-border overflow-hidden">
                    {items.map((entity, i) => (
                      <div key={i} className="flex items-center gap-3 px-3 py-2 bg-surface-raised">
                        <span className="flex-1 text-sm font-semibold text-text-primary truncate">
                          {entity.value}
                        </span>
                        <span className="text-xs text-text-secondary tabular-nums">
                          {entity.confidence.toFixed(3)}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
