"use client";

import { useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { DocumentUpload } from "@/components/documents/DocumentUpload";
import { DocumentTable } from "@/components/documents/DocumentTable";
import { useDocuments } from "@/hooks/use-documents";
import type { FilterTab } from "@/components/documents/StatusFilterTabs";

export default function DocumentsPage() {
  const searchParams = useSearchParams();
  const router = useRouter();

  const statusParam = searchParams.get("status");
  const currentFilter: FilterTab = (statusParam as FilterTab) ?? "all";
  const [page, setPage] = useState(1);
  const perPage = 25;

  const { data, isLoading } = useDocuments(page, perPage, currentFilter === "all" ? undefined : currentFilter);
  const { data: allData } = useDocuments(1, 1000, undefined);

  const counts: Record<FilterTab, number> | undefined = allData?.items
    ? {
        all: allData.total,
        pending: allData.items.filter((d) => d.status === "pending").length,
        processing: allData.items.filter((d) => d.status === "processing").length,
        processed: allData.items.filter((d) => d.status === "processed").length,
        failed: allData.items.filter((d) => d.status === "failed").length,
      }
    : undefined;

  const handleFilterChange = useCallback(
    (tab: FilterTab) => {
      const params = new URLSearchParams(searchParams.toString());
      if (tab === "all") {
        params.delete("status");
      } else {
        params.set("status", tab);
      }
      setPage(1);
      router.replace(`/documents?${params.toString()}`);
    },
    [searchParams, router],
  );

  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  return (
    <div className="animate-fade-up flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border px-6 py-3">
        <h1 className="text-xl font-semibold text-gray-900">Documents</h1>
      </div>

      <div className="flex flex-1 flex-col gap-6 overflow-y-auto p-6">
        <DocumentUpload />

        <DocumentTable
          data={data}
          isLoading={isLoading}
          page={page}
          perPage={perPage}
          onPageChange={handlePageChange}
          currentFilter={currentFilter}
          onFilterChange={handleFilterChange}
          counts={counts}
        />
      </div>
    </div>
  );
}
