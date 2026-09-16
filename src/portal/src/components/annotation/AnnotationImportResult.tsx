"use client";

import { useMemo, useState } from "react";
import { SlideOver, Spinner } from "@/components/ui";
import type { ImportState } from "@/hooks/use-annotation-import";
import { useEntityTypes } from "@/hooks/use-entity-types";
import { useImportTypeMap, TypeMapEntry } from "@/hooks/use-import-type-map";

export interface AnnotationImportResultProps {
  open: boolean;
  state: ImportState;
  onDone: () => void;
}

export function AnnotationImportResult({
  open,
  state,
  onDone,
}: AnnotationImportResultProps) {
  const entityTypes = useEntityTypes();
  const typeMap = useImportTypeMap();
  const [choices, setChoices] = useState<Record<string, string>>({});

  const unmapped =
    state.status === "success" ? state.result.unmapped_types ?? [] : [];
  const sourceFile = state.status === "success" ? state.result.source_file : undefined;
  const options = useMemo(
    () => (entityTypes.data?.entity_types ?? []).map((e) => e.name),
    [entityTypes.data],
  );

  function submitMapping() {
    if (!sourceFile) return;
    const mapping: Record<string, TypeMapEntry> = {};
    for (const u of unmapped) {
      const choice = choices[u.type] ?? "__create__";
      mapping[u.type] = choice === "__create__" ? { create: true } : { to: choice };
    }
    typeMap.mutate({ sourceFile, mapping });
  }
  return (
    <SlideOver open={open} onClose={onDone} width={480}>
      <div className="flex flex-col h-full">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <h2 className="text-lg font-semibold text-gray-900">Import Result</h2>
          <button
            type="button"
            onClick={onDone}
            className="text-gray-400 hover:text-gray-600"
          >
            ✕
          </button>
        </div>

        <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4">
          {state.status === "uploading" && (
            <div className="flex items-center justify-center py-12">
              <span className="flex items-center gap-2 text-sm text-gray-500">
                <Spinner size="sm" /> Importing...
              </span>
            </div>
          )}

          {state.status === "success" && (
            <>
              {/* Summary */}
              <div className="rounded-lg border border-status-completed/30 bg-status-completed/5 p-4">
                <p className="text-lg font-semibold text-status-completed">
                  {state.result.imported_count} rows imported
                  {(state.result.pending_count ?? 0) > 0 &&
                    `, ${state.result.pending_count} held for type mapping`}
                </p>
              </div>

              {/* Unmapped types — map each before the file is training-eligible */}
              {unmapped.length > 0 && (
                <div className="rounded-lg border border-status-failed/30 bg-status-failed/5 p-3">
                  <h3 className="mb-2 text-xs font-semibold uppercase tracking-wider text-status-failed">
                    {unmapped.length} entity type{unmapped.length > 1 ? "s" : ""} not defined yet
                  </h3>
                  <p className="mb-2 text-xs text-gray-600">
                    Map each to an existing entity type, or create a new one. Nothing is
                    created until you confirm.
                  </p>
                  <div className="flex flex-col gap-2">
                    {unmapped.map((u) => (
                      <label key={u.type} className="flex items-center gap-2 text-xs">
                        <span className="w-32 shrink-0 font-mono">{u.type}</span>
                        <span className="text-gray-400">({u.row_count})</span>
                        <span aria-hidden>→</span>
                        <select
                          aria-label={`Map ${u.type}`}
                          className="flex-1 rounded border border-border px-2 py-1"
                          value={choices[u.type] ?? "__create__"}
                          onChange={(e) =>
                            setChoices((c) => ({ ...c, [u.type]: e.target.value }))
                          }
                        >
                          <option value="__create__">Create new entity type &ldquo;{u.type}&rdquo;</option>
                          {options.map((name) => (
                            <option key={name} value={name}>
                              {name}
                            </option>
                          ))}
                        </select>
                      </label>
                    ))}
                  </div>
                  <button
                    type="button"
                    disabled={typeMap.isPending}
                    onClick={submitMapping}
                    className="mt-3 rounded-lg bg-brand-primary px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
                  >
                    {typeMap.isPending ? "Mapping…" : "Map types"}
                  </button>
                  {typeMap.isSuccess && (
                    <p className="mt-2 text-xs text-status-completed">
                      Mapped.{" "}
                      {typeMap.data?.training_eligible
                        ? "This file is now training-eligible."
                        : "Some types still need mapping."}
                    </p>
                  )}
                  {typeMap.isError && (
                    <p className="mt-2 text-xs text-status-failed">{typeMap.error.message}</p>
                  )}
                </div>
              )}

              {/* Entity type summary */}
              {Object.keys(state.result.entity_type_counts).length > 0 && (
                <div>
                  <h3 className="mb-2 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                    Entity Type Summary
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {Object.entries(state.result.entity_type_counts).map(([type, count]) => (
                      <span
                        key={type}
                        className="inline-flex items-center gap-1 rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-700"
                      >
                        {type}: {count}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Warnings */}
              {state.result.warnings.length > 0 && (
                <div className="rounded-lg border border-yellow-300/30 bg-yellow-50 p-3">
                  <h3 className="text-xs font-semibold text-yellow-800 uppercase tracking-wider mb-1">
                    Warnings
                  </h3>
                  <ul className="text-xs text-yellow-700 space-y-0.5">
                    {state.result.warnings.map((w, i) => (
                      <li key={i}>
                        Row {w.row_index}: {w.message}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}

          {state.status === "error" && (
            <div className="rounded-lg border border-status-failed/30 bg-status-failed/5 p-4">
              <p className="text-sm font-medium text-status-failed">{state.error}</p>
            </div>
          )}
        </div>

        {/* Actions */}
        {state.status !== "uploading" && (
          <div className="flex items-center justify-end gap-2 border-t border-border px-4 py-3">
            <button
              type="button"
              onClick={onDone}
              className="rounded-lg bg-brand-primary px-4 py-2 text-sm font-medium text-white"
            >
              Done
            </button>
          </div>
        )}
      </div>
    </SlideOver>
  );
}
