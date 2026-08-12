"use client";

import { useState, useRef, useEffect } from "react";
import { ArrowUp } from "lucide-react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled: boolean;
}

// Matches the reading column in MessageThread so the composer lines up with the
// conversation content above it.
const COLUMN_WIDTH = 760;
const MAX_TEXTAREA_HEIGHT = 200;

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState("");
  const [focused, setFocused] = useState(false);
  const [multiline, setMultiline] = useState(false);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const singleLineHeightRef = useRef<number | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Grow with the content up to a cap, then scroll inside the textarea. The
  // one-line height is captured on the first pass so the send button can be
  // centred against a single line and drop to the bottom once the field grows.
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    if (singleLineHeightRef.current === null) {
      singleLineHeightRef.current = el.scrollHeight;
    }
    const next = Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT);
    el.style.height = next + "px";
    setMultiline(next > (singleLineHeightRef.current ?? next) + 1);
  }, [text]);

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  };

  const canSend = !disabled && text.trim().length > 0;

  return (
    <div style={{ padding: "6px 24px 10px", flexShrink: 0 }}>
      <div style={{ maxWidth: COLUMN_WIDTH, margin: "0 auto" }}>
        <div
          onClick={() => inputRef.current?.focus()}
          style={{
            display: "flex",
            alignItems: "flex-end",
            gap: 10,
            padding: "10px 10px 10px 18px",
            borderRadius: 24,
            background: "var(--surface-3)",
            border: "1px solid " + (focused ? "var(--primary-line)" : "var(--line)"),
            boxShadow: "var(--shadow-card)",
            transition: "border-color 120ms ease",
          }}
        >
          <textarea
            ref={inputRef}
            rows={1}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
            placeholder="Type your question..."
            disabled={disabled}
            style={{
              flex: 1,
              minWidth: 0,
              maxHeight: MAX_TEXTAREA_HEIGHT,
              padding: "7px 0",
              border: "none",
              outline: "none",
              resize: "none",
              background: "transparent",
              color: "var(--ink)",
              fontSize: 15,
              lineHeight: 1.5,
              fontFamily: "inherit",
            }}
          />
          <button
            onClick={handleSubmit}
            disabled={!canSend}
            aria-label="Send message"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              alignSelf: multiline ? "flex-end" : "center",
              flexShrink: 0,
              width: 34,
              height: 34,
              borderRadius: 999,
              background: canSend ? "var(--primary)" : "var(--surface-2)",
              color: canSend ? "#fff" : "var(--ink-3)",
              border: canSend ? "none" : "1px solid var(--line)",
              cursor: canSend ? "pointer" : "not-allowed",
              transition: "background 120ms ease",
            }}
          >
            <ArrowUp size={18} />
          </button>
        </div>
      </div>
    </div>
  );
}
