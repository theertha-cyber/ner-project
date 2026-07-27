"use client";

import { useState, useRef, useEffect } from "react";

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled: boolean;
}

export function ChatInput({ onSend, disabled }: ChatInputProps) {
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = () => {
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText("");
  };

  return (
    <div
      style={{
        borderTop: "1px solid var(--line)",
        padding: "12px 16px",
        display: "flex",
        gap: 8,
        background: "var(--surface-3)",
      }}
    >
      <input
        ref={inputRef}
        type="text"
        value={text}
        onChange={(e) => setText(e.target.value)}
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
          border: "1px solid var(--line)",
          borderRadius: 8,
          padding: "10px 12px",
          fontSize: 14,
          outline: "none",
          background: "var(--surface-2)",
          color: "var(--ink)",
        }}
      />
      <button
        onClick={handleSubmit}
        disabled={disabled || !text.trim()}
        style={{
          background: disabled || !text.trim() ? "var(--ink-3)" : "var(--primary)",
          color: "#fff",
          border: "none",
          borderRadius: 8,
          padding: "10px 20px",
          cursor: disabled || !text.trim() ? "not-allowed" : "pointer",
          fontSize: 14,
          fontWeight: 600,
        }}
      >
        {disabled ? "Sending..." : "Send"}
      </button>
    </div>
  );
}
