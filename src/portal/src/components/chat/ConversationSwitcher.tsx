"use client";

import { useState } from "react";

interface Conversation {
  id: string;
  title: string | null;
  created_at: string;
  message_count: number;
}

interface ConversationSwitcherProps {
  conversations: Conversation[];
  activeConvId: string | null;
  onSelect: (id: string) => void;
}

const ROW_HEIGHT = 30;
const VISIBLE_ROWS = 5;

// Compact, permanently visible list of recent conversations for switching
// without leaving the conversation view. Deliberately not a dropdown/popover
// and deliberately not a card: plain text rows on the page background, so it
// reads as navigation rather than a separate component.
export function ConversationSwitcher({
  conversations,
  activeConvId,
  onSelect,
}: ConversationSwitcherProps) {
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  if (conversations.length === 0) return null;

  return (
    <div
      className="scrollbar-none"
      style={{
        width: 172,
        flexShrink: 0,
        maxHeight: ROW_HEIGHT * VISIBLE_ROWS,
        overflowY: "auto",
      }}
    >
      {conversations.map((conv) => {
        const isActive = conv.id === activeConvId;
        const isHovered = hoveredId === conv.id;
        return (
          <button
            key={conv.id}
            type="button"
            onClick={() => onSelect(conv.id)}
            onMouseEnter={() => setHoveredId(conv.id)}
            onMouseLeave={() => setHoveredId(null)}
            title={conv.title || "New conversation"}
            aria-current={isActive ? "true" : undefined}
            style={{
              display: "block",
              width: "100%",
              height: ROW_HEIGHT,
              padding: "0 6px",
              background: isHovered ? "var(--line-2)" : "transparent",
              border: "none",
              borderRadius: "var(--radius-sm)",
              color: isActive ? "var(--ink)" : "var(--ink-3)",
              fontSize: 13,
              fontWeight: isActive ? 600 : 400,
              textAlign: "left",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
              cursor: "pointer",
              transition: "color 120ms ease, background 120ms ease",
            }}
          >
            {conv.title || "New conversation"}
          </button>
        );
      })}
    </div>
  );
}
