"use client";

import { useState } from "react";
import { CitationCard } from "./CitationCard";
import { OriginalDocumentViewer } from "@/components/documents/OriginalDocumentViewer";

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

interface Viewing {
  documentId: string;
  pageNumber: number | null;
  documentName: string | null;
}

export function CitationChips({ citations }: { citations: Citation[] }) {
  const [expandedIndex, setExpandedIndex] = useState<number | null>(null);
  const [showAll, setShowAll] = useState(false);
  // One viewer per message, not per chip: the panel is modal, and several mounted
  // viewers would each hold their own copy of a document in memory.
  const [viewing, setViewing] = useState<Viewing | null>(null);

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
          // Citations from the relational and entity channels carry no document, so
          // there is nothing to open — those chips keep their previous behaviour rather
          // than offering an action that would fail.
          const documentId = citation.document_id ?? null;
          return (
            <span key={i} style={{ display: "inline-flex" }}>
              <button
                onClick={() =>
                  documentId
                    ? setViewing({
                        documentId,
                        pageNumber: citation.page_number ?? null,
                        documentName: citation.document_name ?? null,
                      })
                    : setExpandedIndex(isOpen ? null : i)
                }
                title={documentId ? `Open ${label}` : label}
                aria-label={documentId ? `Open document ${label}` : undefined}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 5,
                  background: isOpen ? "var(--primary)" : "var(--surface-2)",
                  color: isOpen ? "#fff" : "var(--ink-2)",
                  border: "1px solid var(--line)",
                  borderRight: documentId ? "none" : "1px solid var(--line)",
                  borderRadius: documentId ? "999px 0 0 999px" : 999,
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
              {/* The snippet and relevance detail shown before this change stay reachable:
                  a chip that opens a document would otherwise lose them entirely. */}
              {documentId && (
                <button
                  onClick={() => setExpandedIndex(isOpen ? null : i)}
                  aria-label={`Show citation details for ${label}`}
                  aria-expanded={isOpen}
                  style={{
                    background: isOpen ? "var(--primary)" : "var(--surface-2)",
                    color: isOpen ? "#fff" : "var(--ink-3)",
                    border: "1px solid var(--line)",
                    borderRadius: "0 999px 999px 0",
                    padding: "3px 8px",
                    fontSize: 12,
                    lineHeight: 1.3,
                    cursor: "pointer",
                  }}
                >
                  {isOpen ? "▴" : "▾"}
                </button>
              )}
            </span>
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
      <OriginalDocumentViewer
        documentId={viewing?.documentId ?? null}
        pageNumber={viewing?.pageNumber ?? null}
        documentName={viewing?.documentName ?? null}
        onClose={() => setViewing(null)}
      />
    </div>
  );
}
