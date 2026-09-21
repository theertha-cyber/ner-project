"use client";

import { useEffect, useRef, useState } from "react";
import { Paperclip } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ChartRenderer, type ChartPayload } from "./ChartRenderer";
import { CitationChips } from "./CitationChips";
import { MessageFeedback, type Feedback } from "./MessageFeedback";
import { ExportCard, type ExportAvailability } from "./ExportCard";
import { OriginalDocumentViewer } from "@/components/documents/OriginalDocumentViewer";
import { TruncatableReply } from "./TruncatableReply";

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
  attachments?: MessageAttachment[] | null;
}

export interface MessageAttachment {
  id: string;
  filename: string;
  mime_type?: string | null;
  file_size_bytes?: number | null;
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
  // One viewer for the whole thread. An attachment chip opens the same panel a
  // citation chip does — they sit a few pixels apart and behaving differently would
  // read as a bug.
  const [viewingAttachment, setViewingAttachment] = useState<
    { documentId: string; documentName: string; siblings: MessageAttachment[] } | null
  >(null);

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
                      {msg.attachments && msg.attachments.length > 0 && (
                        <div
                          aria-label="Message attachments"
                          role="group"
                          style={{
                            display: "flex",
                            flexWrap: "wrap",
                            gap: 6,
                            marginBottom: 8,
                          }}
                        >
                          {msg.attachments.map((file) => (
                            <button
                              key={file.id}
                              type="button"
                              onClick={() =>
                                setViewingAttachment({
                                  documentId: file.id,
                                  documentName: file.filename,
                                  siblings: msg.attachments ?? [],
                                })
                              }
                              title={`Open ${file.filename}`}
                              aria-label={`Open attachment ${file.filename}`}
                              style={{
                                cursor: "pointer",
                                color: "inherit",
                                font: "inherit",
                                display: "inline-flex",
                                alignItems: "center",
                                gap: 6,
                                maxWidth: 220,
                                padding: "3px 10px",
                                borderRadius: "var(--radius-pill)",
                                // Sits inside the primary-filled user bubble, so the chip
                                // is a translucent overlay rather than a surface token.
                                background: "rgba(255, 255, 255, 0.18)",
                                border: "1px solid rgba(255, 255, 255, 0.35)",
                                fontSize: 12.5,
                                lineHeight: 1.5,
                              }}
                            >
                              <Paperclip size={12} aria-hidden="true" />
                              <span
                                style={{
                                  overflow: "hidden",
                                  textOverflow: "ellipsis",
                                  whiteSpace: "nowrap",
                                }}
                              >
                                {file.filename}
                              </span>
                            </button>
                          ))}
                        </div>
                      )}
                      {msg.content}
                    </div>
                  </div>
                </div>
              );
            }

            const showTrailers = !msg.isThinking && !msg.isStreaming;

            return (
              <div key={msg.id} style={{ marginBottom: 36 }}>
                {msg.isThinking ? (
                  <span style={{ color: "var(--ink-3)", fontSize: 15 }} className="thinking-dots">
                    Thinking...
                  </span>
                ) : showTrailers ? (
                  <TruncatableReply content={msg.content} />
                ) : (
                  <div className="chat-markdown chat-doc">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  </div>
                )}

                {/* Chart and export both hang off the same structured rows, so a turn
                    with results can show both. Truncation (above, via TruncatableReply)
                    and the export offer (below) are independent: a turn's reply may
                    truncate, may have an export, both, or neither, in any combination. */}
                {msg.chart && <ChartRenderer chart={msg.chart} />}
                {showTrailers && msg.export && <ExportCard export_={msg.export} />}

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

      <OriginalDocumentViewer
        documentId={viewingAttachment?.documentId ?? null}
        documentName={viewingAttachment?.documentName ?? null}
        otherSources={(viewingAttachment?.siblings ?? [])
          .filter((file) => file.id !== viewingAttachment?.documentId)
          .map((file) => ({ documentId: file.id, documentName: file.filename }))}
        onSelectSource={(source) =>
          setViewingAttachment({
            documentId: source.documentId,
            documentName: source.documentName ?? "Document",
            siblings: viewingAttachment?.siblings ?? [],
          })
        }
        onClose={() => setViewingAttachment(null)}
      />
    </div>
  );
}
