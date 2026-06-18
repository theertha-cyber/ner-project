"use client";

import { useState } from "react";
import type { ConfirmedSpan } from "./span-reducer";

interface EntityType {
  id: string;
  name: string;
}

interface SpanInspectorProps {
  span: ConfirmedSpan;
  entityTypes: EntityType[];
  onRetype: (spanId: string, entityType: string) => void;
  onDelete: (spanId: string) => void;
  onClose: () => void;
}

export function SpanInspector({ span, entityTypes, onRetype, onDelete, onClose }: SpanInspectorProps) {
  const [selectedType, setSelectedType] = useState(span.entityType);
  const [isRetypeOpen, setIsRetypeOpen] = useState(false);

  const handleRetype = () => {
    if (selectedType !== span.entityType) {
      onRetype(span.id, selectedType);
    } else {
      setIsRetypeOpen(false);
    }
  };

  return (
    <div
      style={{
        position: "absolute",
        bottom: 16,
        right: 16,
        width: 280,
        background: "var(--color-surface-raised)",
        border: "1px solid var(--color-border)",
        borderRadius: 10,
        boxShadow: "0 4px 20px rgba(0,0,0,0.12)",
        zIndex: 20,
        padding: "14px 16px",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
        <span
          style={{
            fontSize: 12,
            fontWeight: 600,
            color: "var(--color-text-secondary)",
            textTransform: "uppercase",
            letterSpacing: "0.06em",
          }}
        >
          Span Inspector
        </span>
        <button
          onClick={onClose}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            color: "var(--color-text-secondary)",
            fontSize: 16,
            lineHeight: 1,
            padding: 2,
          }}
          aria-label="Close inspector"
        >
          ✕
        </button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 13 }}>
        <Row label="Text" value={`"${span.text}"`} />
        <Row label="Type" value={span.entityType} />
        <Row label="Start" value={String(span.charStart)} />
        <Row label="End" value={String(span.charEnd)} />
        <Row label="Confidence" value={span.confidence.toFixed(2)} />
      </div>

      <div style={{ marginTop: 14, display: "flex", flexDirection: "column", gap: 8 }}>
        {isRetypeOpen ? (
          <div style={{ display: "flex", gap: 6 }}>
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              style={{
                flex: 1,
                fontSize: 13,
                padding: "4px 8px",
                borderRadius: 6,
                border: "1px solid var(--color-border)",
                background: "var(--color-surface)",
                color: "var(--color-text-primary)",
              }}
            >
              {entityTypes.map((et) => (
                <option key={et.id} value={et.name}>
                  {et.name}
                </option>
              ))}
            </select>
            <button
              onClick={handleRetype}
              style={{
                padding: "4px 10px",
                background: "var(--color-primary)",
                color: "#fff",
                border: "none",
                borderRadius: 6,
                fontSize: 12,
                cursor: "pointer",
              }}
            >
              Apply
            </button>
          </div>
        ) : (
          <button
            onClick={() => setIsRetypeOpen(true)}
            style={{
              padding: "6px 0",
              background: "var(--color-primary-soft, rgba(99,102,241,0.1))",
              color: "var(--color-primary)",
              border: "none",
              borderRadius: 6,
              fontSize: 13,
              cursor: "pointer",
              fontWeight: 500,
            }}
          >
            Retype
          </button>
        )}
        <button
          onClick={() => onDelete(span.id)}
          style={{
            padding: "6px 0",
            background: "rgba(239,68,68,0.1)",
            color: "var(--color-error, #ef4444)",
            border: "none",
            borderRadius: 6,
            fontSize: 13,
            cursor: "pointer",
            fontWeight: 500,
          }}
        >
          Delete span
        </button>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between" }}>
      <span style={{ color: "var(--color-text-secondary)" }}>{label}</span>
      <span
        style={{
          color: "var(--color-text-primary)",
          fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
          fontSize: 12,
        }}
      >
        {value}
      </span>
    </div>
  );
}
