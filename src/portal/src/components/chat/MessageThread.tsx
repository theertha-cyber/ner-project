"use client";

import { useEffect, useRef } from "react";
import { CitationCard } from "./CitationCard";

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
}

interface MessageThreadProps {
  messages: Message[];
  loading: boolean;
}

function isCitation(s: Source | Citation): s is Citation {
  return "document_name" in s;
}

function SourceCitation({ source }: { source: Source }) {
  return (
    <CitationCard
      citation={{
        document_name: null,
        document_id: source.document_id,
        entity_type: source.entity_type,
        entity_value: source.value,
        confidence: source.confidence,
        context_snippet: source.source_type === "document_chunk" ? source.chunk_text : null,
        source_type: source.source_type,
      }}
    />
  );
}

export function MessageThread({ messages, loading }: MessageThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const empty = messages.length === 0;

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: "16px" }}>
      {loading && (
        <div style={{ textAlign: "center", padding: 16, color: "#9ca3af" }}>Loading...</div>
      )}
      {empty && !loading && (
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            height: "100%",
            color: "#9ca3af",
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
                {msg.sources.map((source, i) =>
                  isCitation(source) ? (
                    <CitationCard key={i} citation={source} />
                  ) : (
                    <SourceCitation key={i} source={source} />
                  )
                )}
              </div>
            )}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
