"use client";

import { useEffect, useRef, useState } from "react";

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

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
  created_at: string;
}

interface MessageThreadProps {
  messages: Message[];
  loading: boolean;
}

function SourceCitation({ source }: { source: Source }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div
      style={{
        marginTop: 4,
        fontSize: 12,
        color: "#6b7280",
      }}
    >
      <button
        onClick={() => setExpanded(!expanded)}
        style={{
          background: "none",
          border: "none",
          color: "#2563eb",
          cursor: "pointer",
          padding: 0,
          fontSize: 12,
          textDecoration: "underline",
        }}
      >
        {expanded ? "Hide" : "Show"} source: {source.source_type}
        {source.document_id ? ` (${source.document_id.slice(0, 8)}...)` : ""}
      </button>
      {expanded && (
        <div
          style={{
            marginTop: 4,
            padding: "6px 8px",
            background: "#f3f4f6",
            borderRadius: 6,
            fontSize: 12,
            lineHeight: 1.4,
          }}
        >
          {source.source_type === "document_chunk" && source.chunk_text && (
            <div>
              <strong>Text:</strong> {source.chunk_text.slice(0, 200)}
              {source.chunk_text.length > 200 ? "..." : ""}
              <br />
              {source.relevance_score !== undefined && (
                <span>
                  <strong>Relevance:</strong> {(source.relevance_score * 100).toFixed(0)}%
                </span>
              )}
            </div>
          )}
          {source.source_type === "sql" && source.value && (
            <div>
              <strong>Data:</strong> {source.value.slice(0, 200)}
            </div>
          )}
          {source.source_type === "ner" && (
            <div>
              {source.entity_type && (
                <span>
                  <strong>Type:</strong> {source.entity_type}
                  <br />
                </span>
              )}
              {source.value && (
                <span>
                  <strong>Value:</strong> {source.value}
                  <br />
                </span>
              )}
              {source.confidence !== undefined && (
                <span>
                  <strong>Confidence:</strong> {(source.confidence * 100).toFixed(0)}%
                </span>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function MessageThread({ messages, loading }: MessageThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "16px" }}>
      {loading && (
        <div style={{ textAlign: "center", padding: 16, color: "#9ca3af" }}>Loading...</div>
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
                background: msg.role === "user" ? "#2563eb" : "#f3f4f6",
                color: msg.role === "user" ? "white" : "#111827",
                fontSize: 14,
                lineHeight: 1.4,
                borderBottomRightRadius: msg.role === "user" ? 4 : 12,
                borderBottomLeftRadius: msg.role === "assistant" ? 4 : 12,
              }}
            >
              {msg.content}
            </div>
            {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
              <div style={{ marginTop: 4 }}>
                {msg.sources.map((source, i) => (
                  <SourceCitation key={i} source={source} />
                ))}
              </div>
            )}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
