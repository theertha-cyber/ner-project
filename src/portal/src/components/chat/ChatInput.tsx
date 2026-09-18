"use client";

import { useState, useRef, useEffect } from "react";
import { ArrowUp, Paperclip, X } from "lucide-react";

export interface StagedFile {
  id: string;
  name: string;
  size: number;
  type: string;
  // The real file. Its content is what the send transmits: the backend ingests the
  // bytes so the attachment becomes answerable in this conversation (CAP-6), which a
  // name and a byte count could never do.
  file: File;
}

interface ChatInputProps {
  onSend: (message: string) => void;
  disabled: boolean;
  stagedFiles: StagedFile[];
  onAttach: (files: File[]) => void;
  onRemoveFile: (id: string) => void;
  // True while a send carrying these files is in flight. The upload and the indexing
  // that follows it both happen inside that request, so the tray says so rather than
  // looking idle for what can be several seconds.
  uploading?: boolean;
}

// Matches the reading column in MessageThread so the composer lines up with the
// conversation content above it.
const COLUMN_WIDTH = 760;
const MAX_TEXTAREA_HEIGHT = 200;

// Mirrors the backend allow-list (ALLOWED_EXTENSIONS in
// src/document_service/services/ocr_worker.py) so the client rejects the same
// file set the server accepts (FR-002).
const ATTACH_ACCEPTED_EXTENSIONS = ".pdf,.jpg,.jpeg,.png,.tif,.tiff,.doc,.docx,.csv";

const SUPPORTED_EXTENSIONS = new Set(
  ATTACH_ACCEPTED_EXTENSIONS.split(",").map((ext) => ext.toLowerCase())
);

function isSupportedFile(name: string): boolean {
  const dot = name.lastIndexOf(".");
  if (dot < 0) return false;
  return SUPPORTED_EXTENSIONS.has(name.slice(dot).toLowerCase());
}

export function ChatInput({
  onSend,
  disabled,
  stagedFiles,
  onAttach,
  onRemoveFile,
  uploading = false,
}: ChatInputProps) {
  const [text, setText] = useState("");
  const [focused, setFocused] = useState(false);
  const [multiline, setMultiline] = useState(false);
  const [rejection, setRejection] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
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

  // Staged files never enable send by themselves: the send control stays
  // disabled while the message is empty, and the `disabled` prop forces it off
  // (e.g. while a turn is in flight).
  const canSend = !disabled && text.trim().length > 0;

  const handleFilePick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files ?? []);
    // Keep the input reset so the same file can be picked again later.
    e.target.value = "";
    const supported = selected.filter((f) => isSupportedFile(f.name));
    const rejectedCount = selected.length - supported.length;
    if (supported.length > 0) onAttach(supported);
    setRejection(
      rejectedCount > 0
        ? "Some files were not attached. Supported types: PDF, JPG, JPEG, PNG, TIF, TIFF, DOC, DOCX, CSV."
        : null
    );
  };

  return (
    <div style={{ padding: "6px 24px 10px", flexShrink: 0 }}>
      <div style={{ maxWidth: COLUMN_WIDTH, margin: "0 auto" }}>
        <div
          onClick={() => inputRef.current?.focus()}
          style={{
            display: "flex",
            alignItems: "flex-end",
            gap: 10,
            padding: "10px 10px 10px 12px",
            borderRadius: "var(--radius-xl)",
            background: "var(--surface-3)",
            border: "1px solid " + (focused ? "var(--primary-line)" : "var(--line)"),
            boxShadow: "var(--shadow-card)",
            transition: "border-color 120ms ease",
          }}
        >
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            aria-label="Attach a file"
            title="Attach a file"
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              alignSelf: multiline ? "flex-end" : "center",
              flexShrink: 0,
              width: 34,
              height: 34,
              borderRadius: "var(--radius-pill)",
              background: "var(--surface)",
              color: "var(--ink-2)",
              border: "1px solid var(--line)",
              cursor: "pointer",
              transition: "border-color 120ms ease, color 120ms ease",
            }}
          >
            <Paperclip size={18} />
          </button>
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
              borderRadius: "var(--radius-pill)",
              background: canSend ? "var(--primary)" : "var(--surface-2)",
              color: canSend ? "#fff" : "var(--ink-3)",
              border: canSend ? "none" : "1px solid var(--line)",
              cursor: canSend ? "pointer" : "not-allowed",
              transition: "background 120ms ease",
            }}
          >
            <ArrowUp size={18} />
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={ATTACH_ACCEPTED_EXTENSIONS}
            style={{ display: "none" }}
            onChange={handleFilePick}
          />
        </div>

        {rejection && (
          <div
            role="alert"
            style={{
              marginTop: 8,
              padding: "7px 12px",
              background: "var(--bad-soft)",
              border: "1px solid var(--bad-soft)",
              borderRadius: "var(--radius-md)",
              color: "var(--bad)",
              fontSize: 12.5,
              lineHeight: 1.4,
            }}
          >
            {rejection}
          </div>
        )}

        {stagedFiles.length > 0 && (
          <div
            role="region"
            aria-label="Staged attachments"
            style={{
              display: "flex",
              flexWrap: "wrap",
              alignItems: "center",
              gap: 8,
              paddingTop: 10,
            }}
          >
            {stagedFiles.map((file) => (
              <span
                key={file.id}
                title={file.name}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  maxWidth: 240,
                  padding: "4px 6px 4px 10px",
                  background: "var(--surface-3)",
                  border: "1px solid var(--line)",
                  borderRadius: "var(--radius-pill)",
                  color: "var(--ink)",
                  fontSize: 13,
                  lineHeight: 1.4,
                }}
              >
                <span
                  aria-hidden="true"
                  style={{
                    width: 6,
                    height: 6,
                    flexShrink: 0,
                    borderRadius: "var(--radius-pill)",
                    background: "var(--good)",
                  }}
                />
                <span
                  style={{
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                  }}
                >
                  {file.name}
                </span>
                <button
                  type="button"
                  onClick={() => onRemoveFile(file.id)}
                  disabled={uploading}
                  aria-label={"Remove " + file.name}
                  title={"Remove " + file.name}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    flexShrink: 0,
                    width: 20,
                    height: 20,
                    borderRadius: "var(--radius-pill)",
                    border: "none",
                    background: "transparent",
                    color: "var(--ink-2)",
                    cursor: "pointer",
                    padding: 0,
                    transition: "color 120ms ease, background 120ms ease",
                  }}
                >
                  <X size={13} aria-hidden="true" />
                </button>
              </span>
            ))}
            <span
              role={uploading ? "status" : undefined}
              style={{
                color: "var(--ink-2)",
                fontSize: 12.5,
                lineHeight: 1.4,
                padding: "2px 2px",
              }}
            >
              {uploading
                ? "Uploading and preparing attachments…"
                : "Staging does not reserve the conversation until send."}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}