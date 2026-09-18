"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/auth-fetch";
import { buildTokenMap } from "@/lib/token-map";
import { Spinner } from "@/components/ui";
import { useToast } from "@/hooks/use-toast";
import { DocumentViewer } from "@/components/annotation/DocumentViewer";
import { initialSpanState } from "@/components/annotation/span-reducer";
import type { ConfirmedSpan } from "@/components/annotation/span-reducer";
import type { EntityType } from "@/types/entity-types";
import type { AcceptanceSuggestion, SuggestionDisposition } from "@/types/seed-bootstrap";

const DISPOSITION_OPTIONS: { value: SuggestionDisposition; label: string; hint: string }[] = [
  { value: "agree", label: "Correct", hint: "Right type, right boundaries" },
  { value: "boundary", label: "Wrong span", hint: "Right type, boundaries need fixing" },
  { value: "retype", label: "Wrong type", hint: "Real entity, wrong label" },
  { value: "reject", label: "Not an entity", hint: "Should not be here at all" },
];

interface RawSpan {
  id: string;
  entity_type: string;
  char_start: number;
  char_end: number;
  text_content?: string;
  text?: string;
  confidence?: number;
}

interface BatchReviewDocumentProps {
  documentId: string;
  filename: string;
  suggestions: AcceptanceSuggestion[];
  /** Scoring controls (Correct/Wrong span/...) for the sample-agreement review. Omit both to
   * hide them — used in the plain "confirm suggestions" list, which isn't part of any sample. */
  dispositions?: Record<string, SuggestionDisposition>;
  onDisposition?: (suggestionId: string, disposition: SuggestionDisposition) => void;
  /** When provided, each suggestion gets a "Add to training data" button that promotes it
   * straight into confirmed spans via the ordinary per-document promote endpoint — the salvage
   * path for a batch whose bulk accept is closed (design.md: sub-threshold batches keep their
   * suggestions available for per-document review, not a rejection that discards them). */
  onPromote?: (suggestionId: string) => void | Promise<void>;
  entityColors: Record<string, string>;
  entityTypes: EntityType[];
  /** Decided reviews are shown for the record but not edited. */
  readOnly?: boolean;
}

/**
 * One sampled document in the acceptance review: its full text with the LLM's pre-labeled
 * spans highlighted in place (dashed), the reviewer's own spans on top of it (solid), and the
 * controls to disposition a suggestion or add a label the model missed. Manual spans are saved
 * to the document as they are drawn — the same `/spans` endpoint and gesture as the annotation
 * workspace.
 */
export function BatchReviewDocument({
  documentId,
  filename,
  suggestions,
  dispositions = {},
  onDisposition,
  onPromote,
  entityColors,
  entityTypes,
  readOnly,
}: BatchReviewDocumentProps) {
  const { toast } = useToast();
  const [promotingId, setPromotingId] = useState<string | null>(null);

  const handlePromote = useCallback(
    async (suggestionId: string, text: string) => {
      if (!onPromote) return;
      setPromotingId(suggestionId);
      try {
        await onPromote(suggestionId);
        toast(`Added "${text}" to training data`, "ok");
      } catch (err) {
        toast(err instanceof Error ? err.message : "Failed to add to training data", "bad");
      } finally {
        setPromotingId(null);
      }
    },
    [onPromote, toast],
  );

  const { data, isLoading, isError } = useQuery({
    queryKey: ["document-text", documentId],
    queryFn: async () => {
      const res = await authFetch(`/api/v1/documents/${documentId}/text`);
      if (!res.ok) throw new Error(`Failed to load document text: ${res.status}`);
      return (await res.json()) as { text: string };
    },
  });
  const docText = data?.text ?? "";
  const tokenMap = useMemo(() => (docText ? buildTokenMap(docText) : []), [docText]);

  // The reviewer's own labels for this document, loaded once and then kept in step with each
  // save/delete so the highlight and the list never disagree.
  const [manualSpans, setManualSpans] = useState<ConfirmedSpan[]>([]);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await authFetch(`/api/v1/documents/${documentId}/spans`);
      if (!res.ok || cancelled) return;
      const rows = (await res.json()) as RawSpan[];
      if (cancelled) return;
      setManualSpans(
        rows.map((r) => ({
          id: r.id,
          entityType: r.entity_type,
          charStart: r.char_start,
          charEnd: r.char_end,
          text: r.text_content ?? r.text ?? "",
          confidence: r.confidence ?? 1,
        })),
      );
    })();
    return () => {
      cancelled = true;
    };
  }, [documentId]);

  const [armedType, setArmedType] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState<number | null>(null);
  const [dragEnd, setDragEnd] = useState<number | null>(null);
  const suppressClick = useRef(false);

  const activeTypes = useMemo(() => entityTypes.filter((et) => et.is_active), [entityTypes]);

  const spanState = useMemo(
    () => ({
      ...initialSpanState,
      confirmed: manualSpans,
      suggested: suggestions.map((s) => ({
        id: s.id,
        entityType: s.entity_type,
        charStart: s.char_start,
        charEnd: s.char_end,
        text: s.text,
        confidence: 0,
      })),
      armedType,
    }),
    [manualSpans, suggestions, armedType],
  );

  const createSpan = useCallback(
    async (charStart: number, charEnd: number) => {
      if (!armedType || readOnly) return;
      const spanText = docText.slice(charStart, charEnd).trim();
      if (!spanText) return;
      // Don't stack a manual span on top of one that's already there.
      if (manualSpans.some((s) => s.charStart < charEnd && s.charEnd > charStart)) return;

      const res = await authFetch(`/api/v1/documents/${documentId}/spans`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          entity_type: armedType,
          char_start: charStart,
          char_end: charEnd,
          text: spanText,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        toast(
          (err as { detail?: { message?: string } }).detail?.message ?? "Failed to save annotation",
          "bad",
        );
        return;
      }
      const d = (await res.json()) as RawSpan;
      setManualSpans((prev) => [
        ...prev,
        {
          id: d.id,
          entityType: d.entity_type,
          charStart: d.char_start,
          charEnd: d.char_end,
          text: d.text_content ?? d.text ?? spanText,
          confidence: d.confidence ?? 1,
        },
      ]);
      toast(`Labeled “${spanText}” as ${armedType}`, "ok");
    },
    [armedType, readOnly, docText, manualSpans, documentId, toast],
  );

  const deleteSpan = useCallback(
    async (spanId: string) => {
      const res = await authFetch(`/api/v1/documents/${documentId}/spans/${spanId}`, {
        method: "DELETE",
      });
      if (res.ok || res.status === 204) {
        setManualSpans((prev) => prev.filter((s) => s.id !== spanId));
      } else {
        toast("Failed to remove annotation", "bad");
      }
    },
    [documentId, toast],
  );

  const handleTokenClick = useCallback(
    (tokenIndex: number) => {
      if (suppressClick.current) {
        suppressClick.current = false;
        return;
      }
      if (!armedType) return;
      const entry = tokenMap[tokenIndex];
      if (entry) createSpan(entry.charStart, entry.charEnd);
    },
    [armedType, tokenMap, createSpan],
  );

  const handleMouseDown = useCallback(
    (tokenIndex: number) => {
      if (!armedType) return;
      setIsDragging(true);
      setDragStart(tokenIndex);
      setDragEnd(tokenIndex);
    },
    [armedType],
  );

  const handleMouseEnter = useCallback(
    (tokenIndex: number) => {
      if (isDragging) setDragEnd(tokenIndex);
    },
    [isDragging],
  );

  useEffect(() => {
    const onMouseUp = () => {
      if (!isDragging || dragStart === null) {
        setIsDragging(false);
        setDragStart(null);
        setDragEnd(null);
        return;
      }
      const a = Math.min(dragStart, dragEnd ?? dragStart);
      const b = Math.max(dragStart, dragEnd ?? dragStart);
      setIsDragging(false);
      setDragStart(null);
      setDragEnd(null);
      if (a === b) return; // a plain click — the click handler owns it
      suppressClick.current = true;
      if (tokenMap[a] && tokenMap[b]) createSpan(tokenMap[a].charStart, tokenMap[b].charEnd);
    };
    document.addEventListener("mouseup", onMouseUp);
    return () => document.removeEventListener("mouseup", onMouseUp);
  }, [isDragging, dragStart, dragEnd, tokenMap, createSpan]);

  return (
    <div className="rounded-lg border border-border" style={{ background: "var(--surface-1)" }}>
      <div
        className="flex items-center justify-between border-b px-4 py-2.5"
        style={{ borderColor: "var(--line)" }}
      >
        <span className="font-body text-sm font-medium" style={{ color: "var(--ink)" }}>
          {filename}
        </span>
        <span className="font-body text-xs" style={{ color: "var(--ink-3)" }}>
          {suggestions.length} model {suggestions.length === 1 ? "suggestion" : "suggestions"}
          {manualSpans.length > 0 && ` · ${manualSpans.length} added`}
        </span>
      </div>

      {!readOnly && activeTypes.length > 0 && (
        <div
          className="flex flex-wrap items-center gap-1.5 border-b px-4 py-2.5"
          style={{ borderColor: "var(--line)" }}
        >
          <span className="font-body text-xs" style={{ color: "var(--ink-3)" }}>
            {armedType
              ? "Click a word or drag across several to label them:"
              : "To add a missing entity, pick its type then click/drag the text:"}
          </span>
          {activeTypes.map((et) => {
            const color = entityColors[et.name] ?? "#94a3b8";
            const isArmed = armedType === et.name;
            return (
              <button
                key={et.id}
                type="button"
                onClick={() => setArmedType(isArmed ? null : et.name)}
                className="flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-xs"
                style={{
                  borderColor: isArmed ? color : "var(--line)",
                  background: isArmed ? color + "22" : "transparent",
                  color: isArmed ? "var(--ink)" : "var(--ink-2)",
                }}
              >
                <span className="inline-block size-2 rounded-sm" style={{ background: color }} />
                {et.name}
              </button>
            );
          })}
        </div>
      )}

      <div className="flex flex-col gap-4 p-4 lg:flex-row">
        <div className="min-w-0 flex-1">
          {isLoading ? (
            <div className="flex justify-center py-8">
              <Spinner size="sm" />
            </div>
          ) : isError ? (
            <p className="font-body text-sm" style={{ color: "var(--bad)" }}>
              Could not load this document&apos;s text.
            </p>
          ) : (
            <DocumentViewer
              tokenMap={tokenMap}
              spanState={spanState}
              entityColors={entityColors}
              onTokenClick={handleTokenClick}
              onTokenMouseDown={readOnly ? undefined : handleMouseDown}
              onTokenMouseEnter={readOnly ? undefined : handleMouseEnter}
              isDragging={isDragging}
              dragStartIndex={dragStart}
              dragEndIndex={dragEnd}
            />
          )}
        </div>

        <aside className="flex w-full flex-col gap-4 lg:w-80 lg:shrink-0">
          <div className="flex flex-col gap-2">
            <span
              className="font-body text-xs font-semibold uppercase tracking-wide"
              style={{ color: "var(--ink-3)" }}
            >
              Model suggestions
            </span>
            {suggestions.length === 0 ? (
              <p className="font-body text-xs italic" style={{ color: "var(--ink-3)" }}>
                The model pre-labeled nothing in this document.
              </p>
            ) : (
              suggestions.map((suggestion) => {
                const color = entityColors[suggestion.entity_type] ?? "#94a3b8";
                return (
                  <div
                    key={suggestion.id}
                    className="rounded-lg border border-border p-2.5"
                    style={{ background: "var(--surface-2)" }}
                  >
                    <div className="mb-1.5 flex items-center gap-2">
                      <span
                        className="inline-block size-2.5 shrink-0 rounded-sm"
                        style={{ background: color }}
                      />
                      <span className="font-mono text-xs" style={{ color: "var(--ink-2)" }}>
                        {suggestion.entity_type}
                      </span>
                    </div>
                    <p className="mb-2 font-body text-sm" style={{ color: "var(--ink)" }}>
                      {suggestion.text}
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {onDisposition &&
                        DISPOSITION_OPTIONS.map((option) => {
                          const active = dispositions[suggestion.id] === option.value;
                          return (
                            <button
                              key={option.value}
                              type="button"
                              disabled={readOnly}
                              title={option.hint}
                              onClick={() => onDisposition(suggestion.id, option.value)}
                              className="rounded border px-2 py-1 font-body text-xs disabled:cursor-default"
                              style={{
                                borderColor: active ? "var(--primary-line)" : "var(--line)",
                                background: active ? "var(--surface-3)" : "transparent",
                                color: active ? "var(--ink)" : "var(--ink-3)",
                              }}
                            >
                              {option.label}
                            </button>
                          );
                        })}
                      {onPromote && (
                        <button
                          type="button"
                          disabled={readOnly || promotingId === suggestion.id}
                          title="Save this exactly as suggested, as a confirmed training label"
                          onClick={() => handlePromote(suggestion.id, suggestion.text)}
                          className="rounded bg-brand-primary px-2 py-1 font-body text-xs font-medium text-white disabled:cursor-default disabled:opacity-50"
                        >
                          {promotingId === suggestion.id ? "Adding…" : "Add to training data"}
                        </button>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>

          <div className="flex flex-col gap-2">
            <span
              className="font-body text-xs font-semibold uppercase tracking-wide"
              style={{ color: "var(--ink-3)" }}
            >
              Your annotations
            </span>
            {manualSpans.length === 0 ? (
              <p className="font-body text-xs italic" style={{ color: "var(--ink-3)" }}>
                {readOnly
                  ? "None added."
                  : "None yet — label anything the model missed using the text on the left."}
              </p>
            ) : (
              manualSpans.map((span) => {
                const color = entityColors[span.entityType] ?? "#94a3b8";
                return (
                  <div
                    key={span.id}
                    className="flex items-center gap-2 rounded-lg border border-border p-2"
                    style={{ background: "var(--surface-2)" }}
                  >
                    <span
                      className="inline-block size-2.5 shrink-0 rounded-sm"
                      style={{ background: color }}
                    />
                    <span
                      className="min-w-0 flex-1 truncate font-body text-sm"
                      style={{ color: "var(--ink)" }}
                      title={span.text}
                    >
                      <span className="font-mono text-xs" style={{ color: "var(--ink-3)" }}>
                        {span.entityType}
                      </span>{" "}
                      {span.text}
                    </span>
                    {!readOnly && (
                      <button
                        type="button"
                        onClick={() => deleteSpan(span.id)}
                        aria-label="Remove annotation"
                        className="shrink-0 rounded px-1.5 py-0.5 font-body text-xs"
                        style={{ color: "var(--ink-3)" }}
                      >
                        ✕
                      </button>
                    )}
                  </div>
                );
              })
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
