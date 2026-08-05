"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { DocumentRow } from "./DocumentRow";
import { StatusFilterTabs } from "./StatusFilterTabs";
import type { FilterTab } from "./StatusFilterTabs";
import { authFetch } from "@/lib/auth-fetch";
import { useToast } from "@/hooks/use-toast";
import { useState, useCallback } from "react";
import type { DocumentListResponse } from "@/types/documents";

const SKELETON_ROWS = 4;

function SkeletonRows() {
  return (
    <>
      {Array.from({ length: SKELETON_ROWS }).map((_, i) => (
        <tr key={i} className="animate-pulse" style={{ borderBottom: "1px solid var(--line)" }}>
          <td className="px-4 py-3"><div className="h-4 w-40 rounded" style={{ background: "var(--surface-3)" }} /></td>
          <td className="px-4 py-3"><div className="h-4 w-12 rounded" style={{ background: "var(--surface-3)" }} /></td>
          <td className="px-4 py-3"><div className="h-4 w-16 rounded" style={{ background: "var(--surface-3)" }} /></td>
          <td className="px-4 py-3"><div className="h-5 w-20 rounded-full" style={{ background: "var(--surface-3)" }} /></td>
          <td className="px-4 py-3"><div className="h-4 w-24 rounded" style={{ background: "var(--surface-3)" }} /></td>
          <td className="px-4 py-3"><div className="h-4 w-4 rounded" style={{ background: "var(--surface-3)" }} /></td>
        </tr>
      ))}
    </>
  );
}

export interface DocumentTableProps {
  data: DocumentListResponse | undefined;
  isLoading: boolean;
  page: number;
  perPage: number;
  onPageChange: (page: number) => void;
  currentFilter: FilterTab;
  onFilterChange: (tab: FilterTab) => void;
  counts?: Record<FilterTab, number>;
  search?: string;
  onSearchChange?: (value: string) => void;
}

export function DocumentTable({
  data,
  isLoading,
  page,
  perPage,
  onPageChange,
  currentFilter,
  onFilterChange,
  counts,
  search,
  onSearchChange,
}: DocumentTableProps) {
  const [slideOutId, setSlideOutId] = useState<string | null>(null);
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      const res = await authFetch(`/api/v1/documents/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error(`Delete failed: ${res.status}`);
    },
    onMutate: async (id) => {
      if (currentFilter === "all") {
        const queryKey = ["documents"];
        const prev = queryClient.getQueryData<DocumentListResponse>(queryKey);
        if (prev) {
          queryClient.setQueryData<DocumentListResponse>(queryKey, {
            ...prev,
            documents: prev.documents.map((d) =>
              d.id === id ? { ...d, status: "deleted" as const } : d,
            ),
          });
        }
        toast("Document deleted", "ok");
      } else {
        setSlideOutId(id);
        toast("Document deleted", "ok");
      }
    },
    onSuccess: (_data, id) => {
      if (currentFilter !== "all") {
        setTimeout(() => {
          setSlideOutId(null);
          queryClient.invalidateQueries({ queryKey: ["documents"] });
        }, 300);
      }
    },
    onError: () => {
      toast("Failed to delete document", "bad");
      setSlideOutId(null);
      queryClient.invalidateQueries({ queryKey: ["documents"] });
    },
  });

  const handleDelete = useCallback(
    (id: string) => {
      deleteMutation.mutate(id);
    },
    [deleteMutation],
  );

  const totalPages = data ? Math.ceil(data.total / perPage) : 0;
  const items = data?.documents ?? [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3">
        <StatusFilterTabs selected={currentFilter} onChange={onFilterChange} counts={counts} />
        {onSearchChange && (
          <div className="relative">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 20 20"
              fill="currentColor"
              className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2"
              style={{ color: "var(--ink-3)" }}
            >
              <path fillRule="evenodd" d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z" clipRule="evenodd" />
            </svg>
            <input
              type="text"
              value={search ?? ""}
              onChange={(e) => onSearchChange(e.target.value)}
              placeholder="Search documents..."
              className="w-56 rounded-md border py-1.5 pl-8 pr-3 text-sm outline-none"
              style={{ borderColor: "var(--line)", background: "var(--surface-3)", color: "var(--ink)" }}
            />
          </div>
        )}
      </div>

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b" style={{ borderColor: "var(--line)", background: "var(--surface-3)" }}>
              <th className="px-4 py-3 text-xs font-medium uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>Filename</th>
              <th className="px-4 py-3 text-xs font-medium uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>Type</th>
              <th className="px-4 py-3 text-xs font-medium uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>Size</th>
              <th className="px-4 py-3 text-xs font-medium uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>Status</th>
              <th className="px-4 py-3 text-xs font-medium uppercase tracking-wider" style={{ color: "var(--ink-3)" }}>Created</th>
              <th className="px-4 py-3 text-xs font-medium uppercase tracking-wider text-right" style={{ color: "var(--ink-3)" }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <SkeletonRows />
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-sm" style={{ color: "var(--ink-3)" }}>
                  No documents yet — upload your first document
                </td>
              </tr>
            ) : (
              items.map((doc) => (
                <DocumentRow
                  key={doc.id}
                  doc={doc}
                  onDelete={handleDelete}
                  isDeleting={deleteMutation.isPending && deleteMutation.variables === doc.id}
                  isRemoving={slideOutId === doc.id && currentFilter !== "all"}
                />
              ))
            )}
          </tbody>
        </table>
      </div>

      {!isLoading && data && data.total > perPage && (
        <div className="flex items-center justify-between text-sm" style={{ color: "var(--ink-3)" }}>
          <span>
            Showing {(page - 1) * perPage + 1}–
            {Math.min(page * perPage, data.total)} of {data.total}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-40"
              style={{ color: "var(--ink-2)" }}
            >
              Previous
            </button>
            <button
              type="button"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              className="rounded-md px-3 py-1.5 text-sm font-medium disabled:opacity-40"
              style={{ color: "var(--ink-2)" }}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
