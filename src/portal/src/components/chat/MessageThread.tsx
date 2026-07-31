"use client";

import { useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { CitationChips } from "./CitationChips";

interface Source {
  source_type: string;
  document_id?: string;
  chunk_index?: number;
  chunk_text?: string;
  relevance_score?: number;
  entity_type?: string;
  value?: string;
  confidence?: number;
}

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

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: (Source | Citation)[];
  created_at: string;
  isThinking?: boolean;
}

interface MessageThreadProps {
  messages: Message[];
  loading: boolean;
}

function isCitation(s: Source | Citation): s is Citation {
  return "document_name" in s;
}

function toCitation(s: Source | Citation): Citation {
  if (isCitation(s)) return s;
  return {
    document_name: null,
    document_id: s.document_id,
    entity_type: s.entity_type,
    entity_value: s.value,
    confidence: s.confidence,
    relevance_score: s.relevance_score,
    context_snippet: s.source_type === "document_chunk" ? s.chunk_text : null,
    source_type: s.source_type,
  };
}

export function MessageThread({ messages, loading }: MessageThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const empty = messages.length === 0;

  return (
    <div style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "16px" }}>
      {loading && (
        <div style={{ textAlign: "center", padding: 16, color: "var(--ink-3)" }}>Loading...</div>
      )}
      {empty && !loading && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            height: "100%",
            color: "var(--ink-3)",
            fontSize: 14,
          }}
        >
          Send a message to start
        </div>
      )}
      {messages.map((msg) => (
        <div
          key={msg.id}
          style={{
            display: "flex",
            justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
            marginBottom: 12,
          }}
        >
          <div style={{ maxWidth: "75%" }}>
            <div
              style={{
                padding: "10px 14px",
                borderRadius: 12,
                background: msg.role === "user" ? "var(--primary)" : "var(--surface-2)",
                color: msg.role === "user" ? "#fff" : "var(--ink)",
                fontSize: 14,
                lineHeight: 1.4,
                borderBottomRightRadius: msg.role === "user" ? 4 : 12,
                borderBottomLeftRadius: msg.role === "assistant" ? 4 : 12,
              }}
            >
              {msg.isThinking ? (
                <span style={{ color: "var(--ink-3)" }} className="thinking-dots">
                  Thinking...
                </span>
              ) : msg.role === "assistant" ? (
                <div className="chat-markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                </div>
              ) : (
                msg.content
              )}
            </div>
            {!msg.isThinking && msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
              <CitationChips citations={msg.sources.map(toCitation)} />
            )}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
