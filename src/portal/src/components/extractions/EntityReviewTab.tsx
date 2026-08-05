"use client";

import { useState, useMemo } from "react";
import { useEntities, type ReviewFilter } from "@/hooks/use-entities";
import { EntityRow } from "./EntityRow";
import { Spinner } from "@/components/ui";

const FILTERS: { value: ReviewFilter; label: string }[] = [
  { value: "all", label: "all" },
  { value: "unreviewed", label: "unreviewed" },
  { value: "confirmed", label: "confirmed" },
  { value: "corrected", label: "corrected" },
  { value: "rejected", label: "rejected" },
];

function cleanEntityType(label: string): string {
  return label.replace(/^[BI]-/, "");
}

function groupEntities<T extends { entity_id: string }>(entities: T[]): Map<string, T[]> {
  const groups = new Map<string, T[]>();
  for (const entity of entities) {
    const type = cleanEntityType(entity.entity_id);
    if (!groups.has(type)) groups.set(type, []);
    groups.get(type)!.push(entity);
  }
  return groups;
}

export function EntityReviewTab() {
  const [filter, setFilter] = useState<ReviewFilter>("all");
  const { entities, total, isLoading, confirm, reject } = useEntities(filter);

  const groups = useMemo(() => groupEntities(entities), [entities]);
  const sortedTypeKeys = useMemo(
    () => [...groups.keys()].sort((a, b) => a.localeCompare(b)),
    [groups]
  );
  const typeCount = groups.size;

  return (
    <div className="flex flex-col gap-4">
      {/* Filter pill row */}
      <div className="flex items-center gap-3 flex-wrap">
        <div className="flex items-center gap-1">
          {FILTERS.map((f) => {
            const active = f.value === filter;
            return (
              <button
                key={f.value}
                type="button"
                onClick={() => setFilter(f.value)}
                className={[
                  "rounded-lg px-3 py-1 text-sm font-medium transition-colors",
                  active
                    ? "text-white"
                    : "text-text-secondary hover:text-text-primary",
                ].join(" ")}
                style={active ? { background: "var(--primary)" } : undefined}
              >
                {f.label}
              </button>
            );
          })}
        </div>
        <span className="ml-auto font-mono text-xs text-text-secondary">
          {total} entities · {typeCount} types · GET /entities
        </span>
      </div>

      {/* Entity groups */}
      <div className="flex flex-col gap-5">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Spinner />
          </div>
        ) : entities.length === 0 ? (
          <p className="py-12 text-center text-sm text-text-secondary">
            No entities found for this filter.
          </p>
        ) : (
          sortedTypeKeys.map((type) => {
            const items = groups.get(type)!;
            return (
              <div key={type}>
                <div className="flex items-center gap-2 mb-1 px-1">
                  <span className="text-xs font-semibold text-text-primary tracking-wider uppercase">
                    {type}
                  </span>
                  <span className="text-[10px] text-text-secondary font-mono">
                    {items.length}
                  </span>
                </div>
                <div className="rounded-xl border border-border bg-surface-raised overflow-hidden"
                  style={{ boxShadow: "var(--shadow-card)" }}>
                  <div>
                    {items.map((entity) => (
                      <EntityRow
                        key={entity.id}
                        entity={entity}
                        onConfirm={confirm}
                        onReject={reject}
                      />
                    ))}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
