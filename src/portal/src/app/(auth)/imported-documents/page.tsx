"use client";

import { useState, useEffect, useMemo, useCallback, useReducer } from "react";
import { useAuth } from "@/lib/auth";
import { useEntityTypes } from "@/hooks/use-entity-types";
import { authFetch } from "@/lib/auth-fetch";
import { Token } from "@/components/annotation/Token";
import type { TokenHighlight } from "@/components/annotation/Token";
import {
  tokenRangeReducer,
  initialTokenRangeState,
  tagsToSpans,
  spansToTags,
  nextSpanId,
} from "@/components/annotation/token-range-reducer";
import type { TokenRangeSpan } from "@/components/annotation/token-range-reducer";

const ENTITY_COLORS = [
  "#6366f1", "#f59e0b", "#10b981", "#ef4444", "#8b5cf6",
  "#3b82f6", "#f97316", "#ec4899", "#14b8a6", "#84cc16",
];

function buildEntityColors(entityTypes: { name: string }[]): Record<string, string> {
  const colors: Record<string, string> = {};
  entityTypes.forEach((et, i) => {
    colors[et.name] = ENTITY_COLORS[i % ENTITY_COLORS.length];
  });
  return colors;
}

interface ImportedRow {
  id: string;
  source_file: string;
  row_index: number;
  entity_types: string[];
  reviewed: boolean;
  reviewed_at: string | null;
  reviewed_by: string | null;
}

interface ImportedRowDetail extends ImportedRow {
  tokens: string[];
  tags: string[];
  created_at: string | null;
}

interface ListResponse {
  items: ImportedRow[];
  total: number;
  page: number;
  per_page: number;
}

function ImportedDocumentsList({
  onSelectRow,
}: {
  onSelectRow: (id: string) => void;
}) {
  const { user } = useAuth();
  const [data, setData] = useState<ListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [sourceFileFilter, setSourceFileFilter] = useState("");
  const [entityTypeFilter, setEntityTypeFilter] = useState("");
  const [reviewedFilter, setReviewedFilter] = useState<string>("");
  const perPage = 20;

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set("page", String(page));
      params.set("per_page", String(perPage));
      if (sourceFileFilter) params.set("source_file", sourceFileFilter);
      if (entityTypeFilter) params.set("entity_type", entityTypeFilter);
      if (reviewedFilter) params.set("reviewed", reviewedFilter);

      const res = await authFetch(`/api/v1/imported-annotations?${params.toString()}`);
      if (res.ok) {
        setData(await res.json());
      }
    } finally {
      setLoading(false);
    }
  }, [page, sourceFileFilter, entityTypeFilter, reviewedFilter]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  const totalPages = data ? Math.ceil(data.total / perPage) : 0;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b px-6 py-3" style={{ borderColor: "var(--line)" }}>
        <h1 className="text-xl font-semibold" style={{ color: "var(--ink)" }}>Imported Documents</h1>
      </div>

      <div className="flex items-center gap-3 border-b px-6 py-3" style={{ borderColor: "var(--line)" }}>
        <input
          placeholder="Filter by source file"
          value={sourceFileFilter}
          onChange={(e) => { setSourceFileFilter(e.target.value); setPage(1); }}
          className="rounded border px-3 py-1.5 text-sm"
          style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}
        />
        <input
          placeholder="Filter by entity type"
          value={entityTypeFilter}
          onChange={(e) => { setEntityTypeFilter(e.target.value); setPage(1); }}
          className="rounded border px-3 py-1.5 text-sm"
          style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}
        />
        <select
          value={reviewedFilter}
          onChange={(e) => { setReviewedFilter(e.target.value); setPage(1); }}
          className="rounded border px-3 py-1.5 text-sm"
          style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}
        >
          <option value="">All</option>
          <option value="true">Reviewed</option>
          <option value="false">Unreviewed</option>
        </select>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {loading ? (
          <div className="text-sm" style={{ color: "var(--ink-3)" }}>Loading...</div>
        ) : !data || data.items.length === 0 ? (
          <div className="text-sm" style={{ color: "var(--ink-3)" }}>No imported documents found.</div>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b text-xs uppercase" style={{ borderColor: "var(--line)", color: "var(--ink-3)" }}>
                <th className="pb-2 pr-4 font-medium">Source File</th>
                <th className="pb-2 pr-4 font-medium">Row</th>
                <th className="pb-2 pr-4 font-medium">Entity Types</th>
                <th className="pb-2 pr-4 font-medium">Reviewed</th>
                <th className="pb-2 font-medium" />
              </tr>
            </thead>
            <tbody>
              {data.items.map((row) => (
                <tr key={row.id} className="border-b hover:bg-gray-50 dark:hover:bg-gray-800" style={{ borderColor: "var(--line)" }}>
                  <td className="py-2 pr-4">{row.source_file}</td>
                  <td className="py-2 pr-4">{row.row_index}</td>
                  <td className="py-2 pr-4">
                    {row.entity_types.map((et) => (
                      <span
                        key={et}
                        className="mr-1 inline-block rounded bg-blue-100 px-1.5 py-0.5 text-xs font-medium text-blue-700"
                      >
                        {et}
                      </span>
                    ))}
                  </td>
                  <td className="py-2 pr-4">
                    {row.reviewed ? (
                      <span className="text-green-600 dark:text-green-400">Yes</span>
                    ) : (
                      <span className="text-amber-600 dark:text-amber-400">No</span>
                    )}
                  </td>
                  <td className="py-2">
                    <button
                      onClick={() => onSelectRow(row.id)}
                      className="rounded bg-blue-600 px-3 py-1 text-xs font-medium text-white hover:bg-blue-700"
                    >
                      Review
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t px-6 py-3" style={{ borderColor: "var(--line)" }}>
          <span className="text-sm" style={{ color: "var(--ink-3)" }}>
            Page {page} of {totalPages} ({data?.total ?? 0} total)
          </span>
          <div className="flex gap-2">
            <button
              disabled={page <= 1}
              onClick={() => setPage((p) => p - 1)}
              className="rounded border px-3 py-1 text-sm disabled:opacity-40"
              style={{ borderColor: "var(--line)" }}
            >
              Previous
            </button>
            <button
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              className="rounded border px-3 py-1 text-sm disabled:opacity-40"
              style={{ borderColor: "var(--line)" }}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function ImportedDocumentReview({
  annotationId,
  onBack,
}: {
  annotationId: string;
  onBack: () => void;
}) {
  const { user } = useAuth();
  const { data: entityTypesData } = useEntityTypes();
  const entityTypes: { name: string }[] = entityTypesData?.entity_types ?? [];
  const entityColors = useMemo(() => buildEntityColors(entityTypes), [entityTypes]);
  const knownTypeNames = useMemo(
    () => new Set(entityTypes.map((et) => et.name.toLowerCase())),
    [entityTypes],
  );

  const [detail, setDetail] = useState<ImportedRowDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragStartIdx, setDragStartIdx] = useState<number | null>(null);
  const [dragEndIdx, setDragEndIdx] = useState<number | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const [spanState, dispatch] = useReducer(tokenRangeReducer, initialTokenRangeState);

  useEffect(() => {
    setLoading(true);
    authFetch(`/api/v1/imported-annotations/${annotationId}`)
      .then(async (res) => {
        if (!res.ok) throw new Error("Failed to load");
        const data: ImportedRowDetail = await res.json();
        setDetail(data);
        const spans = tagsToSpans(data.tags);
        dispatch({ type: "SPANS_LOAD", spans });
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [annotationId]);

  const handleSave = useCallback(async () => {
    if (!detail) return;
    setSaving(true);
    setError(null);
    const tags = spansToTags(spanState.spans, detail.tokens.length);
    const res = await authFetch(`/api/v1/imported-annotations/${annotationId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tags }),
    });
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      setError((body as { detail?: { message?: string } }).detail?.message ?? "Save failed");
      setSaving(false);
      return;
    }
    const updated: ImportedRowDetail = await res.json();
    setDetail(updated);
    setSaved(true);
    setSaving(false);
    setTimeout(() => setSaved(false), 2000);
  }, [detail, spanState.spans, annotationId]);

  const handleMarkReviewed = useCallback(async () => {
    setSaving(true);
    setError(null);
    const res = await authFetch(`/api/v1/imported-annotations/${annotationId}/mark-reviewed`, {
      method: "POST",
    });
    if (!res.ok) {
      setError("Failed to mark reviewed");
      setSaving(false);
      return;
    }
    const updated: ImportedRowDetail = await res.json();
    setDetail(updated);
    setSaved(true);
    setSaving(false);
    setTimeout(() => setSaved(false), 2000);
  }, [annotationId]);

  const handleRetype = useCallback((spanId: string, newType: string) => {
    if (!knownTypeNames.has(newType.toLowerCase())) {
      setError(`Unknown entity type: ${newType}`);
      return;
    }
    setError(null);
    dispatch({ type: "SPAN_RETYPE", spanId, entityType: newType });
  }, [knownTypeNames]);

  const handleDelete = useCallback((spanId: string) => {
    setError(null);
    dispatch({ type: "SPAN_DELETE", spanId });
  }, []);

  const handleTokenMouseDown = useCallback((tokenIndex: number) => {
    if (!spanState.armedType) return;
    setIsDragging(true);
    setDragStartIdx(tokenIndex);
    setDragEndIdx(tokenIndex);
  }, [spanState.armedType]);

  const handleTokenMouseEnter = useCallback((tokenIndex: number) => {
    if (!isDragging) return;
    setDragEndIdx(tokenIndex);
  }, [isDragging]);

  const handleTokenMouseUp = useCallback(() => {
    if (!isDragging || dragStartIdx === null || dragEndIdx === null || !spanState.armedType) {
      setIsDragging(false);
      setDragStartIdx(null);
      setDragEndIdx(null);
      return;
    }
    const start = Math.min(dragStartIdx, dragEndIdx);
    const end = Math.max(dragStartIdx, dragEndIdx);

    if (!knownTypeNames.has(spanState.armedType.toLowerCase())) {
      setError(`Unknown entity type: ${spanState.armedType}`);
      setIsDragging(false);
      setDragStartIdx(null);
      setDragEndIdx(null);
      return;
    }
    setError(null);

    const newSpan: TokenRangeSpan = {
      id: nextSpanId(),
      entityType: spanState.armedType,
      startToken: start,
      endToken: end,
    };
    dispatch({ type: "SPAN_CREATE", span: newSpan });
    setIsDragging(false);
    setDragStartIdx(null);
    setDragEndIdx(null);
  }, [isDragging, dragStartIdx, dragEndIdx, spanState.armedType, knownTypeNames]);

  const userRole = user?.role;
  const isDisabled = userRole !== "annotator" && userRole !== "tenant_admin";

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-sm text-gray-500">Loading...</div>
      </div>
    );
  }

  if (error && !detail) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-sm text-red-500">{error}</div>
      </div>
    );
  }

  if (!detail) return null;

  const currentTags = spansToTags(spanState.spans, detail.tokens.length);

  function getTokenHighlight(tokenIndex: number): TokenHighlight {
    const dragActive = isDragging && dragStartIdx !== null && dragEndIdx !== null;
    if (dragActive) {
      const start = Math.min(dragStartIdx!, dragEndIdx!);
      const end = Math.max(dragStartIdx!, dragEndIdx!);
      if (tokenIndex >= start && tokenIndex <= end && spanState.armedType) {
        const color = entityColors[spanState.armedType] ?? "#94a3b8";
        return { kind: "drag-preview", color };
      }
    }

    for (const span of spanState.spans) {
      if (tokenIndex >= span.startToken && tokenIndex <= span.endToken) {
        const color = entityColors[span.entityType] ?? "#94a3b8";
        return { kind: "confirmed", color };
      }
    }
    return { kind: "none" };
  }

  return (
    <div className="flex h-full flex-col" onMouseUp={handleTokenMouseUp}>
      <div className="flex items-center justify-between border-b border-border px-6 py-3">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="rounded border px-3 py-1 text-sm hover:bg-gray-50 dark:hover:bg-gray-800"
            style={{ borderColor: "var(--line)" }}
          >
            ← Back
          </button>
          <h2 className="text-lg font-semibold">
            {detail.source_file} : row {detail.row_index}
          </h2>
        </div>
        <div className="flex items-center gap-2">
          {saved && <span className="text-sm text-green-600">Saved ✓</span>}
          {detail.reviewed && (
            <span className="text-xs text-green-600">
              Reviewed {detail.reviewed_at ? `at ${new Date(detail.reviewed_at).toLocaleString()}` : ""}
              {detail.reviewed_by ? ` by ${detail.reviewed_by}` : ""}
            </span>
          )}
          <button
            onClick={handleMarkReviewed}
            disabled={saving || detail.reviewed || isDisabled}
            className="rounded border border-green-600 px-3 py-1 text-sm text-green-600 hover:bg-green-50 disabled:opacity-40"
          >
            Mark Reviewed
          </button>
          <button
            onClick={handleSave}
            disabled={saving || isDisabled}
            className="rounded bg-blue-600 px-4 py-1 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-40"
          >
            {saving ? "Saving..." : "Save"}
          </button>
        </div>
      </div>

      {error && (
        <div className="border-b border-red-200 bg-red-50 px-6 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        <div className="flex-1 overflow-y-auto p-6">
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <span className="text-sm font-medium" style={{ color: "var(--ink-2)" }}>Entity Palette:</span>
            {entityTypes.map((et) => {
              const color = entityColors[et.name] ?? "#94a3b8";
              const isArmed = spanState.armedType === et.name;
              return (
                <button
                  key={et.name}
                  onClick={() => {
                    if (!isDisabled) {
                      dispatch(isArmed ? { type: "DISARM" } : { type: "ARM", entityType: et.name });
                    }
                  }}
                  disabled={isDisabled}
                  style={{
                    background: isArmed ? color : "transparent",
                    color: isArmed ? "#fff" : color,
                    border: `2px solid ${color}`,
                  }}
                  className="rounded px-3 py-1 text-xs font-medium transition-all disabled:opacity-40"
                >
                  {et.name}
                </button>
              );
            })}
          </div>

          {spanState.armedType && (
            <div className="mb-4 rounded px-4 py-2 text-sm text-blue-700 dark:text-blue-300" style={{ background: "var(--primary-soft)" }}>
              Click and drag across tokens to create a <strong>{spanState.armedType}</strong> span.
            </div>
          )}

          <div className="flex flex-wrap items-baseline gap-0 rounded-lg border p-4 leading-relaxed" style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}>
            {detail.tokens.map((token, idx) => (
              <Token
                key={`${idx}-${token}`}
                token={token}
                highlight={getTokenHighlight(idx)}
                onClick={() => {
                  if (spanState.selectedSpanId) {
                    dispatch({ type: "SPAN_SET_SELECTED", spanId: null });
                  }
                }}
                onMouseDown={() => handleTokenMouseDown(idx)}
                onMouseEnter={() => handleTokenMouseEnter(idx)}
              />
            ))}
          </div>
        </div>

        <div className="w-72 border-l p-4" style={{ borderColor: "var(--line)" }}>
          <h3 className="mb-3 text-sm font-semibold" style={{ color: "var(--ink-2)" }}>Spans</h3>
          {spanState.spans.length === 0 ? (
            <p className="text-xs" style={{ color: "var(--ink-3)" }}>No spans</p>
          ) : (
            <div className="space-y-2">
              {spanState.spans.map((span) => {
                const color = entityColors[span.entityType] ?? "#94a3b8";
                const selected = spanState.selectedSpanId === span.id;
                return (
                  <div
                    key={span.id}
                    onClick={() => dispatch({ type: "SPAN_SET_SELECTED", spanId: span.id })}
                    style={{
                      borderLeft: `3px solid ${color}`,
                      background: selected ? `${color}11` : "transparent",
                    }}
                    className={`cursor-pointer rounded p-2 transition-colors ${selected ? "" : "hover:bg-gray-50 dark:hover:bg-gray-800"}`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium" style={{ color }}>
                        {span.entityType}
                      </span>
                      <div className="flex gap-1">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(span.id);
                          }}
                          disabled={isDisabled}
                          className="text-xs text-red-500 hover:text-red-700 disabled:opacity-40"
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                    <div className="mt-1 text-[11px]" style={{ color: "var(--ink-3)" }}>
                      tokens {span.startToken}–{span.endToken}
                    </div>
                    {selected && (
                      <div className="mt-2">
                        <select
                          value={span.entityType}
                          onChange={(e) => handleRetype(span.id, e.target.value)}
                          disabled={isDisabled}
                          className="w-full rounded border px-2 py-1 text-xs"
                          style={{ borderColor: "var(--line)" }}
                        >
                          {entityTypes.map((et) => (
                            <option key={et.name} value={et.name}>
                              {et.name}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function ImportedDocumentsPage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const handleSelectRow = useCallback((id: string) => {
    setSelectedId(id);
  }, []);

  const handleBack = useCallback(() => {
    setSelectedId(null);
  }, []);

  if (selectedId) {
    return <ImportedDocumentReview annotationId={selectedId} onBack={handleBack} />;
  }

  return <ImportedDocumentsList onSelectRow={handleSelectRow} />;
}
