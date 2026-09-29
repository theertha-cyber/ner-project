"use client";

import { useState } from "react";

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
  // `tabular_file` citations only (ADR-018): never a row value.
  file_name?: string | null;
  file_version?: number | null;
  sheet?: string | null;
  columns?: string[] | null;
}

export function CitationCard({ citation }: { citation: Citation }) {
  const [expanded, setExpanded] = useState(false);

  const hasContext = !!citation.context_snippet;
  const docName =
    citation.document_name ||
    citation.file_name ||
    (citation.document_id ? citation.document_id.slice(0, 8) + "..." : "Unknown document");
  const isTabular = citation.source_type === "tabular_file";

  return (
    <div
      style={{
        marginTop: 4,
        padding: "8px 10px",
        background: "#f3f4f6",
        borderRadius: 8,
        fontSize: 12,
        lineHeight: 1.4,
        border: "1px solid #e5e7eb",
      }}
    >
      <div style={{ fontWeight: 600, fontSize: 13, color: "#111827", marginBottom: 2 }}>
        {docName}
      </div>
      {isTabular && (
        <div style={{ color: "#4b5563" }}>
          {citation.file_version != null && <span>Version {citation.file_version}</span>}
          {citation.sheet && <span> · Sheet {citation.sheet}</span>}
          {citation.columns && citation.columns.length > 0 && (
            <div>Columns: {citation.columns.join(", ")}</div>
          )}
        </div>
      )}
      <div style={{ color: "#4b5563" }}>
        {citation.entity_type && <span><strong>{citation.entity_type}:</strong> </span>}
        {citation.entity_value && <span>{citation.entity_value}</span>}
        {citation.confidence !== undefined && citation.confidence !== null && (
          <span style={{ color: "#9ca3af", marginLeft: 6 }}>
            ({(citation.confidence * 100).toFixed(0)}%)
          </span>
        )}
      </div>
      {citation.relevance_score !== undefined && citation.relevance_score !== null && (
        <div style={{ color: "#9ca3af", marginTop: 2 }}>
          relevance: {citation.relevance_score.toFixed(3)}
        </div>
      )}
      {hasContext && (
        <>
          <button
            onClick={() => setExpanded(!expanded)}
            style={{
              background: "none",
              border: "none",
              color: "#2563eb",
              cursor: "pointer",
              padding: "2px 0",
              fontSize: 12,
              textDecoration: "underline",
              marginTop: 2,
            }}
          >
            {expanded ? "Hide context" : "Show context"}
          </button>
          {expanded && (
            <div
              style={{
                marginTop: 4,
                padding: "6px 8px",
                background: "white",
                borderRadius: 4,
                fontSize: 12,
                color: "#374151",
                border: "1px solid #e5e7eb",
              }}
            >
              {citation.context_snippet}
            </div>
          )}
        </>
      )}
    </div>
  );
}
