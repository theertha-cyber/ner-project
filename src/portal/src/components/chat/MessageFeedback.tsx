"use client";

import { ThumbsUp, ThumbsDown } from "lucide-react";

export interface Feedback {
  message_id: string;
  rating: "up" | "down";
  created_at: string;
}

interface MessageFeedbackProps {
  messageId: string;
  feedback?: Feedback | null;
  onRate: (messageId: string, rating: "up" | "down") => void;
}

// The rated state is carried by the glyph itself — filled and in a dark accent —
// rather than by a tinted pill behind it, which read as a coloured box swallowing
// the icon at this size.
const BUTTON_BASE: React.CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  width: 26,
  height: 26,
  padding: 0,
  border: "none",
  borderRadius: 6,
  background: "transparent",
};

export function MessageFeedback({ messageId, feedback, onRate }: MessageFeedbackProps) {
  const rated = feedback?.rating ?? null;

  return (
    <div style={{ display: "flex", gap: 4, marginTop: 4 }}>
      <button
        type="button"
        aria-label="Thumbs up"
        aria-pressed={rated === "up"}
        disabled={rated !== null}
        onClick={() => onRate(messageId, "up")}
        style={{
          ...BUTTON_BASE,
          color: rated === "up" ? "var(--good)" : "var(--ink-3)",
          cursor: rated === null ? "pointer" : "default",
          opacity: rated !== null && rated !== "up" ? 0.35 : 1,
        }}
      >
        <ThumbsUp size={15} strokeWidth={rated === "up" ? 2.25 : 1.75} fill={rated === "up" ? "currentColor" : "none"} />
      </button>
      <button
        type="button"
        aria-label="Thumbs down"
        aria-pressed={rated === "down"}
        disabled={rated !== null}
        onClick={() => onRate(messageId, "down")}
        style={{
          ...BUTTON_BASE,
          color: rated === "down" ? "var(--bad)" : "var(--ink-3)",
          cursor: rated === null ? "pointer" : "default",
          opacity: rated !== null && rated !== "down" ? 0.35 : 1,
        }}
      >
        <ThumbsDown size={15} strokeWidth={rated === "down" ? 2.25 : 1.75} fill={rated === "down" ? "currentColor" : "none"} />
      </button>
    </div>
  );
}
