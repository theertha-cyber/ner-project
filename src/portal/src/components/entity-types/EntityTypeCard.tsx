"use client";

import { useState } from "react";
import type { EntityType } from "@/types/entity-types";

const HUE_TABLE = [25, 330, 235, 285, 155, 200, 60];

export interface EntityTypeCardProps {
  entityType: EntityType;
  index: number;
  onEdit: () => void;
  onToggle: () => void;
}

export function EntityTypeCard({ entityType, index, onEdit, onToggle }: EntityTypeCardProps) {
  const [hovered, setHovered] = useState(false);
  const hue = HUE_TABLE[index % 7];

  const mappingEntries = Object.entries(entityType.base_label_mapping);
  const mappingLines = mappingEntries.flatMap(([base, names]) =>
    names.map((n) => `${base} → ${n}`),
  );
  const examplesDisplay = entityType.examples.slice(0, 2).join(", ");

  return (
    <div
      className="rounded-lg border border-border bg-surface p-4 flex flex-col gap-3"
      style={{
        transition: "transform 150ms, border-color 150ms",
        transform: hovered ? "translateY(-2px)" : "none",
        borderColor: hovered ? "var(--primary-line)" : undefined,
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
    >
      {/* Header: dot + name + version */}
      <div className="flex items-start gap-3">
        <div
          className="shrink-0 rounded-md flex items-center justify-center"
          style={{
            width: 34,
            height: 34,
            backgroundColor: `oklch(0.92 0.08 ${hue})`,
          }}
        >
          <div
            className="rounded-full"
            style={{
              width: 12,
              height: 12,
              backgroundColor: `oklch(0.55 0.22 ${hue})`,
            }}
          />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-baseline gap-2">
            <span
              className="font-semibold truncate"
              style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 14.5 }}
            >
              {entityType.name}
            </span>
            <span
              className="text-secondary shrink-0"
              style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10 }}
            >
              v{entityType.version}
            </span>
          </div>
          <p className="text-secondary truncate" style={{ fontSize: 12.5 }}>
            {entityType.description}
          </p>
        </div>
      </div>

      {/* Pills */}
      <div className="flex gap-2 flex-wrap">
        {entityType.required_flag && (
          <span className="rounded-full bg-brand-primary/10 px-2 py-0.5 text-xs font-medium text-brand-primary">
            Required
          </span>
        )}
        <span
          className={[
            "rounded-full px-2 py-0.5 text-xs font-medium",
            entityType.is_active
              ? "bg-status-completed/10 text-status-completed"
              : "bg-gray-100 text-gray-500",
          ].join(" ")}
        >
          {entityType.is_active ? "Active" : "Inactive"}
        </span>
      </div>

      {/* Base label mapping */}
      {mappingLines.length > 0 && (
        <div>
          <p
            className="mb-1 uppercase tracking-wide text-secondary"
            style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5 }}
          >
            Base Label Mapping
          </p>
          <div
            className="rounded bg-surface-secondary px-2 py-1"
            style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 11 }}
          >
            {mappingLines.map((line) => (
              <div key={line}>{line}</div>
            ))}
          </div>
        </div>
      )}

      {/* Examples */}
      {entityType.examples.length > 0 && (
        <div>
          <p
            className="mb-1 uppercase tracking-wide text-secondary"
            style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10.5 }}
          >
            Examples
          </p>
          <p className="text-secondary" style={{ fontSize: 12 }}>
            {examplesDisplay}
          </p>
        </div>
      )}

      {/* Action buttons */}
      <div className="flex gap-2 mt-auto pt-1">
        <button
          type="button"
          onClick={onEdit}
          className="rounded border border-border px-3 py-1.5 text-xs font-medium hover:border-brand-primary hover:text-brand-primary transition-colors"
        >
          Edit
        </button>
        <button
          type="button"
          onClick={onToggle}
          className="rounded border border-border px-3 py-1.5 text-xs font-medium hover:border-brand-primary hover:text-brand-primary transition-colors"
        >
          {entityType.is_active ? "Deactivate" : "Reactivate"}
        </button>
      </div>
    </div>
  );
}
