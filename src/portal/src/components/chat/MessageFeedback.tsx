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
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 26,
          height: 26,
          padding: 0,
          border: "none",
          borderRadius: 6,
          background: rated === "up" ? "var(--good-soft, #dcfce7)" : "transparent",
          color: rated === "up" ? "var(--good, #16a34a)" : "var(--ink-3)",
          cursor: rated === null ? "pointer" : "default",
          opacity: rated !== null && rated !== "up" ? 0.4 : 1,
        }}
      >
        <ThumbsUp size={14} />
      </button>
      <button
        type="button"
        aria-label="Thumbs down"
        aria-pressed={rated === "down"}
        disabled={rated !== null}
        onClick={() => onRate(messageId, "down")}
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: 26,
          height: 26,
          padding: 0,
          border: "none",
          borderRadius: 6,
          background: rated === "down" ? "var(--bad-soft, #fee2e2)" : "transparent",
          color: rated === "down" ? "var(--bad, #dc2626)" : "var(--ink-3)",
          cursor: rated === null ? "pointer" : "default",
          opacity: rated !== null && rated !== "down" ? 0.4 : 1,
        }}
      >
        <ThumbsDown size={14} />
      </button>
    </div>
  );
}
