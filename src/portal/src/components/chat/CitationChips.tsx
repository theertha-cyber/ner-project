"use client";

import { useState } from "react";
import { CitationCard } from "./CitationCard";

interface Citation {
  document_name?: string | null;
  document_id?: string | null;
  entity_type?: string | null;
  entity_value?: string | null;
  confidence?: number | null;
  relevance_score?: number | null;
  context_snippet?: string | null;
  page_number?: number | null;
  source_type?: string;
}

const VISIBLE_COUNT = 2;

export function CitationChips({ citations }: { citations: Citation[] }) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [showAll, setShowAll] = useState(false);

  if (citations.length === 0) return null;

  const visible = showAll ? citations : citations.slice(0, VISIBLE_COUNT);
  const overflow = citations.length - visible.length;

  return (
    <div style={{ marginTop: 6 }}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {visible.map((citation, i) => {
          const label =
            citation.document_name ||
            (citation.document_id ? citation.document_id.slice(0, 8) + "..." : "Source");
          const isOpen = expandedIndex === i;
          return (
            <button
              key={i}
              onClick={() => setExpandedIndex(isOpen ? null : i)}
              title={label}
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: 5,
                background: isOpen ? "var(--primary)" : "var(--surface-2)",
                color: isOpen ? "#fff" : "var(--ink-2)",
                border: "1px solid var(--line)",
                borderRadius: 999,
                padding: "3px 10px 3px 6px",
                fontSize: 12,
                lineHeight: 1.3,
                cursor: "pointer",
                maxWidth: 220,
              }}
            >
              <span
                style={{
                  width: 6,
                  height: 6,
                  borderRadius: "50%",
                  background: isOpen ? "#fff" : "var(--primary)",
                  flexShrink: 0,
                }}
              />
              <span
                style={{
                  overflow: "hidden",
                  textOverflow: "ellipsis",
                  whiteSpace: "nowrap",
                }}
              >
                {label}
              </span>
            </button>
          );
        })}
        {!showAll && overflow > 0 && (
          <button
            onClick={() => setShowAll(true)}
            style={{
              background: "var(--surface-2)",
              color: "var(--ink-3)",
              border: "1px solid var(--line)",
              borderRadius: 999,
              padding: "3px 10px",
              fontSize: 12,
              cursor: "pointer",
            }}
          >
            +{overflow}
          </button>
        )}
      </div>
      {expandedIndex !== null && visible[expandedIndex] && (
        <div style={{ marginTop: 6 }}>
          <CitationCard citation={visible[expandedIndex]} />
        </div>
      )}
    </div>
  );
}
