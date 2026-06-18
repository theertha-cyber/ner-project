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
}

export function DocumentViewer({ tokenMap, spanState, entityColors, onTokenClick }: DocumentViewerProps) {
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

    return highlights;
  }, [tokenMap, spanState.confirmed, spanState.suggested, entityColors]);

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
        />
      ))}
    </div>
  );
}
