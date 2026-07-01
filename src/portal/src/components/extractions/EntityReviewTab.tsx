"use client";

import { useState } from "react";
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

export function EntityReviewTab() {
  const [filter, setFilter] = useState<ReviewFilter>("all");
  const { entities, total, isLoading, confirm, reject } = useEntities(filter);

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
          {total} entities · GET /entities
        </span>
      </div>

      {/* Entity table */}
      <div className="rounded-xl border border-border bg-surface-raised overflow-hidden"
        style={{ boxShadow: "var(--shadow-card)" }}>
        {/* Table header */}
        <div
          className="grid gap-4 px-4 py-2 bg-surface border-b border-border"
          style={{ gridTemplateColumns: "140px 1fr 90px 110px 80px" }}
        >
          {["TYPE", "VALUE", "CONFIDENCE", "REVIEW", ""].map((col) => (
            <span key={col} className="font-mono text-[10px] font-semibold text-text-secondary tracking-widest uppercase">
              {col}
            </span>
          ))}
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Spinner />
          </div>
        ) : entities.length === 0 ? (
          <p className="py-12 text-center text-sm text-text-secondary">
            No entities found for this filter.
          </p>
        ) : (
          <div>
            {entities.map((entity) => (
              <EntityRow
                key={entity.id}
                entity={entity}
                onConfirm={confirm}
                onReject={reject}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
