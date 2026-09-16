"use client";

import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChartRenderer, type ChartPayload } from "./ChartRenderer";
import { CitationChips } from "./CitationChips";
import { MessageFeedback, type Feedback } from "./MessageFeedback";
import { ExportCard, type ExportAvailability } from "./ExportCard";

// Truncation is triggered by *result count* (export.row_count), not by how many
// lines the reply happens to render as — a detailed answer about ONE candidate
// (job title, experience, education, each on its own line) is still one result,
// and must show in full. "List every candidate" with 28 results is what this is
// for. Once a turn covers more than this many results, only the first
// PREVIEW_LINE_LIMIT lines are shown by default, with a "See more" toggle to
// reveal the rest and an export card offering the full result as a file.
const PREVIEW_LINE_LIMIT = 5;

function contentLines(content: string): string[] {
  return content.split("\n").filter((line) => line.trim() !== "");
}

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
  isStreaming?: boolean;
  answer_kind?: "answer" | "clarification" | "guardrail_blocked" | "out_of_domain" | null;
  model_version?: string | null;
  feedback?: Feedback | null;
  export?: ExportAvailability | null;
  chart?: ChartPayload | null;
}

interface MessageThreadProps {
  messages: Message[];
  loading: boolean;
  canRate?: boolean;
  onRateMessage?: (messageId: string, rating: "up" | "down") => void;
}

// Reading column width, shared with the composer so the two line up.
const COLUMN_WIDTH = 760;

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

export function MessageThread({ messages, loading, canRate, onRateMessage }: MessageThreadProps) {
  const bottomRef = useRef<HTMLDivElement>(null);
  const [expandedIds, setExpandedIds] = useState<Set<string>>(new Set());

  const toggleExpanded = (id: string) => {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  // Depend on a signal describing the *tail* of the thread, not the array itself:
  // rating an old message replaces `messages` with a new array (same length, same
  // last message), which under a plain `[messages]` dependency yanked the view down
  // to the newest reply. New turns, streamed tokens, and conversation switches all
  // still move this signal, so those keep auto-scrolling.
  const last = messages[messages.length - 1];
  const tailSignal = `${messages.length}|${last?.id ?? ""}|${last?.content.length ?? 0}`;

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [tailSignal]);

  const empty = messages.length === 0;

  return (
    <div style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
      {loading && (
        <div style={{ textAlign: "center", padding: 24, color: "var(--ink-3)", fontSize: 14 }}>
          Loading...
        </div>
      )}

      {empty && !loading && (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            height: "100%",
            padding: "24px",
            textAlign: "center",
          }}
        >
          <h2
            style={{
              fontSize: 28,
              fontWeight: 600,
              color: "var(--ink)",
              letterSpacing: "-0.01em",
              margin: "0 0 10px",
            }}
          >
            How can I help?
          </h2>
          <p
            style={{
              maxWidth: 460,
              fontSize: 14.5,
              lineHeight: 1.6,
              color: "var(--ink-3)",
              margin: 0,
            }}
          >
            Ask about your documents, candidates, entity types, or any information extracted from
            them — answers come back with the sources they were drawn from.
          </p>
        </div>
      )}

      {!empty && (
        <div style={{ maxWidth: COLUMN_WIDTH, margin: "0 auto", padding: "18px 24px 4px" }}>
          {messages.map((msg, i) => {
            if (msg.role === "user") {
              return (
                <div key={msg.id}>
                  {i > 0 && (
                    <div
                      style={{
                        height: 1,
                        background: "var(--line)",
                        margin: "12px 0 28px",
                      }}
                    />
                  )}
                  <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 28 }}>
                    <div
                      style={{
                        maxWidth: "78%",
                        padding: "10px 16px",
                        borderRadius: 18,
                        borderBottomRightRadius: 6,
                        background: "var(--primary)",
                        color: "#fff",
                        fontSize: 15,
                        lineHeight: 1.55,
                        whiteSpace: "pre-wrap",
                        wordBreak: "break-word",
                      }}
                    >
                      {msg.content}
                    </div>
                  </div>
                </div>
              );
            }

            const showTrailers = !msg.isThinking && !msg.isStreaming;
            const lines = showTrailers ? contentLines(msg.content) : [];
            const resultCount = msg.export?.row_count ?? 0;
            const isTruncatable =
              showTrailers && resultCount > PREVIEW_LINE_LIMIT && lines.length > PREVIEW_LINE_LIMIT;
            const expanded = expandedIds.has(msg.id);
            const displayContent =
              isTruncatable && !expanded ? lines.slice(0, PREVIEW_LINE_LIMIT).join("\n\n") : msg.content;

            return (
              <div key={msg.id} style={{ marginBottom: 36 }}>
                {msg.isThinking ? (
                  <span style={{ color: "var(--ink-3)", fontSize: 15 }} className="thinking-dots">
                    Thinking...
                  </span>
                ) : (
                  <div className="chat-markdown chat-doc">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{displayContent}</ReactMarkdown>
                  </div>
                )}

                {/* Chart and export both hang off the same structured rows, so a turn
                    with results can show both. The chart sits directly under the answer:
                    when the text is truncated to a preview it still conveys the whole
                    result at a glance, and the "get the rest" affordances (export card,
                    See more) follow below it. */}
                {msg.chart && <ChartRenderer chart={msg.chart} />}
                {isTruncatable && msg.export && <ExportCard export_={msg.export} />}
                {isTruncatable && (
                  <button
                    type="button"
                    onClick={() => toggleExpanded(msg.id)}
                    style={{
                      marginTop: 8,
                      padding: 0,
                      border: "none",
                      background: "transparent",
                      color: "var(--primary)",
                      fontSize: 13,
                      fontWeight: 500,
                      cursor: "pointer",
                    }}
                  >
                    {expanded ? "See less" : `See more (${lines.length - PREVIEW_LINE_LIMIT} more)`}
                  </button>
                )}

                {showTrailers && msg.sources && msg.sources.length > 0 && (
                  <div style={{ marginTop: 14 }}>
                    <CitationChips citations={msg.sources.map(toCitation)} />
                  </div>
                )}
                {showTrailers && msg.answer_kind === "answer" && canRate && onRateMessage && (
                  <MessageFeedback messageId={msg.id} feedback={msg.feedback} onRate={onRateMessage} />
                )}
              </div>
            );
          })}
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
