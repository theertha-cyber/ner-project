"use client";

import { SlideOver, Spinner } from "@/components/ui";
import { parseFile } from "@/lib/annotation-import-parser";
import { useEntityTypes } from "@/hooks/use-entity-types";
import type { ParseResult } from "@/lib/annotation-import-parser";
import { useEffect, useMemo, useState } from "react";

export interface AnnotationImportPreviewProps {
  open: boolean;
  file: File | null;
  onConfirm: (file: File) => void;
  onClose: () => void;
}

type PreviewState =
  | { status: "parsing" }
  | { status: "parsed"; result: ParseResult }
  | { status: "error"; error: string };

export function AnnotationImportPreview({
  open,
  file,
  onConfirm,
  onClose,
}: AnnotationImportPreviewProps) {
  const { data: entityTypesData } = useEntityTypes();
  const [previewState, setPreviewState] = useState<PreviewState | null>(null);

  const entityTypeNames = useMemo(
    () => entityTypesData?.entity_types?.map((et) => et.name) ?? [],
    [entityTypesData],
  );

  useEffect(() => {
    if (!open || !file) {
      setPreviewState(null);
      return;
    }

    let cancelled = false;

    if (file.size > 50 * 1024 * 1024) {
      setPreviewState({
        status: "error",
        error: "File exceeds the 50MB maximum",
      });
      return;
    }

    setPreviewState({ status: "parsing" });

    parseFile(file, entityTypeNames).then((result) => {
      if (!cancelled) {
        if (result.error) {
          setPreviewState({ status: "error", error: result.error });
        } else {
          setPreviewState({ status: "parsed", result });
        }
      }
    });

    return () => {
      cancelled = true;
    };
  }, [open, file, entityTypeNames]);

  const formatLabel = previewState?.status === "parsed"
    ? previewState.result.format === "conll" ? "CoNLL" : "JSONL"
    : "";
  const rowLabel = previewState?.status === "parsed"
    ? previewState.result.format === "conll" ? "Sentences" : "Rows"
    : "";

  return (
    <SlideOver open={open} onClose={onClose} width={480}>
      <div className="flex flex-col h-full">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-lg font-semibold text-gray-900">Import Preview</h2>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600"
          >
            ✕
          </button>
        </div>

        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
          {previewState?.status === "parsing" && (
            <div className="flex items-center justify-center py-12">
              <span className="flex items-center gap-2 text-sm text-gray-500">
                <Spinner size="sm" /> Parsing file...
              </span>
            </div>
          )}

          {previewState?.status === "error" && (
            <div className="rounded-lg border border-status-failed/30 bg-status-failed/5 p-4 text-sm text-status-failed">
              {previewState.error}
            </div>
          )}

          {previewState?.status === "parsed" && (
            <>
              {/* Format and row count */}
              <div className="rounded-lg border border-border bg-gray-50 p-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-gray-500">Format</span>
                  <span className="font-medium text-gray-900">{formatLabel}</span>
                </div>
                <div className="flex items-center justify-between mt-1">
                  <span className="text-gray-500">{rowLabel}</span>
                  <span className="font-medium text-gray-900">
                    {previewState.result.rowCount}
                  </span>
                </div>
                <div className="flex items-center justify-between mt-1">
                  <span className="text-gray-500">File</span>
                  <span className="font-medium text-gray-900 truncate max-w-[260px]">
                    {file?.name}
                  </span>
                </div>
              </div>

              {/* Entity type breakdown */}
              <div>
                <h3 className="mb-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                  Entity Type Breakdown
                </h3>
                <div className="flex flex-col gap-1.5">
                  {Object.entries(previewState.result.entityTypeCounts).map(([type, count]) => {
                    const maxCount = Math.max(
                      ...Object.values(previewState.result.entityTypeCounts),
                      1,
                    );
                    const pct = (count / maxCount) * 100;
                    return (
                      <div key={type} className="flex items-center gap-2 text-sm">
                        <span className="w-16 font-medium text-gray-700">{type}</span>
                        <div className="flex-1 h-5 rounded bg-gray-100 overflow-hidden">
                          <div
                            className="h-full rounded bg-indigo-500"
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                        <span className="w-8 text-right text-gray-500">{count}</span>
                      </div>
                    );
                  })}
                  {Object.keys(previewState.result.entityTypeCounts).length === 0 && (
                    <p className="text-sm text-gray-400">No entity types detected</p>
                  )}
                </div>
              </div>

              {/* Unknown type warnings */}
              {previewState.result.unknownTypeWarnings.length > 0 && (
                <div className="rounded-lg border border-yellow-300/30 bg-yellow-50 p-3">
                  <h3 className="text-xs font-semibold text-yellow-800 uppercase tracking-wider mb-1">
                    Unknown Entity Types
                  </h3>
                  <p className="text-sm text-yellow-700 mb-2">
                    {previewState.result.unknownTypeWarnings.length} row(s) contain unknown entity
                    types and will be skipped on import.
                  </p>
                  <ul className="text-xs text-yellow-600 space-y-0.5">
                    {previewState.result.unknownTypeWarnings.map((w, i) => (
                      <li key={i}>
                        Row {w.rowIndex}: {w.unknownTypes.join(", ")}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end gap-2 border-t border-border px-4 py-3">
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-border px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={previewState?.status !== "parsed" || !file}
            onClick={() => file && onConfirm(file)}
            className="rounded-lg bg-brand-primary px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-50"
          >
            {previewState?.status === "parsed"
              ? `Import ${previewState.result.rowCount} rows`
              : "Import"}
          </button>
        </div>
      </div>
    </SlideOver>
  );
}
