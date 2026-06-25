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
        <tr key={i} className="animate-pulse border-b border-gray-100">
          <td className="px-4 py-3"><div className="h-4 w-40 rounded bg-gray-200" /></td>
          <td className="px-4 py-3"><div className="h-4 w-12 rounded bg-gray-200" /></td>
          <td className="px-4 py-3"><div className="h-4 w-16 rounded bg-gray-200" /></td>
          <td className="px-4 py-3"><div className="h-5 w-20 rounded-full bg-gray-200" /></td>
          <td className="px-4 py-3"><div className="h-4 w-24 rounded bg-gray-200" /></td>
          <td className="px-4 py-3"><div className="h-4 w-4 rounded bg-gray-200" /></td>
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
      <StatusFilterTabs selected={currentFilter} onChange={onFilterChange} counts={counts} />

      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-border bg-gray-50">
              <th className="px-4 py-3 text-xs font-medium uppercase tracking-wider text-gray-500">Filename</th>
              <th className="px-4 py-3 text-xs font-medium uppercase tracking-wider text-gray-500">Type</th>
              <th className="px-4 py-3 text-xs font-medium uppercase tracking-wider text-gray-500">Size</th>
              <th className="px-4 py-3 text-xs font-medium uppercase tracking-wider text-gray-500">Status</th>
              <th className="px-4 py-3 text-xs font-medium uppercase tracking-wider text-gray-500">Created</th>
              <th className="px-4 py-3 text-xs font-medium uppercase tracking-wider text-gray-500">Delete</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <SkeletonRows />
            ) : items.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-sm text-gray-500">
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
        <div className="flex items-center justify-between text-sm text-gray-500">
          <span>
            Showing {(page - 1) * perPage + 1}–
            {Math.min(page * perPage, data.total)} of {data.total}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="rounded-md px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100 disabled:text-gray-300"
            >
              Previous
            </button>
            <button
              type="button"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              className="rounded-md px-3 py-1.5 text-sm font-medium text-gray-600 hover:bg-gray-100 disabled:text-gray-300"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
