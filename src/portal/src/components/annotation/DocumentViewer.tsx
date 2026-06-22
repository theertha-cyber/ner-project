"use client";

import { useMemo } from "react";
import { Token, TokenHighlight } from "./Token";
import type { SpanState } from "./span-reducer";
import type { TokenMap } from "@/lib/token-map";
import { spanToTokenRange } from "@/lib/token-map";

interface DocumentViewerProps {
  tokenMap: TokenMap;
  spanState: SpanState;
  entityColors: Record<string, string>;
  onTokenClick: (tokenIndex: number) => void;
  onTokenMouseDown?: (tokenIndex: number) => void;
  onTokenMouseEnter?: (tokenIndex: number) => void;
  isDragging?: boolean;
  dragStartIndex?: number | null;
  dragEndIndex?: number | null;
}

export function DocumentViewer({
  tokenMap,
  spanState,
  entityColors,
  onTokenClick,
  onTokenMouseDown,
  onTokenMouseEnter,
  isDragging,
  dragStartIndex,
  dragEndIndex,
}: DocumentViewerProps) {
  const tokenHighlights = useMemo<TokenHighlight[]>(() => {
    const highlights: TokenHighlight[] = tokenMap.map(() => ({ kind: "none" }));

    // Suggested spans (lower precedence — applied first)
    for (const s of spanState.suggested) {
      const indices = spanToTokenRange(tokenMap, s.charStart, s.charEnd);
      const color = entityColors[s.entityType] ?? "#94a3b8";
      for (const i of indices) {
        if (highlights[i].kind === "none") {
          highlights[i] = { kind: "suggested", color };
        }
      }
    }

    // Confirmed spans (higher precedence — overwrite suggested)
    for (const s of spanState.confirmed) {
      const indices = spanToTokenRange(tokenMap, s.charStart, s.charEnd);
      const color = entityColors[s.entityType] ?? "#94a3b8";
      for (const i of indices) {
        highlights[i] = { kind: "confirmed", color };
      }
    }

    // Drag-preview (highest precedence — only when armed and dragging)
    if (isDragging && spanState.armedType && dragStartIndex !== null && dragStartIndex !== undefined) {
      const minIdx = Math.min(dragStartIndex, dragEndIndex ?? dragStartIndex);
      const maxIdx = Math.max(dragStartIndex, dragEndIndex ?? dragStartIndex);
      const color = entityColors[spanState.armedType] ?? "#94a3b8";
      for (let i = minIdx; i <= maxIdx; i++) {
        if (highlights[i]?.kind !== "confirmed") {
          highlights[i] = { kind: "drag-preview", color };
        }
      }
    }

    return highlights;
  }, [tokenMap, spanState.confirmed, spanState.suggested, spanState.armedType, entityColors, isDragging, dragStartIndex, dragEndIndex]);

  if (tokenMap.length === 0) {
    return (
      <div
        style={{
          padding: "48px 24px",
          color: "var(--color-text-secondary)",
          fontSize: 14,
          textAlign: "center",
        }}
      >
        Select a task from the queue to begin annotating
      </div>
    );
  }

  return (
    <div
      style={{
        lineHeight: "2",
        padding: "4px 0",
      }}
    >
      {tokenMap.map((entry, i) => (
        <Token
          key={i}
          token={entry.token}
          highlight={tokenHighlights[i]}
          onClick={() => onTokenClick(i)}
          onMouseDown={onTokenMouseDown ? () => onTokenMouseDown(i) : undefined}
          onMouseEnter={onTokenMouseEnter ? () => onTokenMouseEnter(i) : undefined}
        />
      ))}
    </div>
  );
}
