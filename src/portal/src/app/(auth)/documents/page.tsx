"use client";

import { useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { DocumentTable } from "@/components/documents/DocumentTable";
import { UploadDialog } from "@/components/documents/UploadDialog";
import { useDocuments } from "@/hooks/use-documents";
import { useAuth } from "@/lib/auth";
import type { FilterTab } from "@/components/documents/StatusFilterTabs";

export default function DocumentsPage() {
  const { user } = useAuth();
  const isTenantAdmin = user?.role === "tenant_admin";

  const searchParams = useSearchParams();
  const router = useRouter();

  const statusParam = searchParams.get("status");
  const currentFilter: FilterTab = (statusParam as FilterTab) ?? "all";
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const perPage = 25;

  const { data, isLoading } = useDocuments(page, perPage, currentFilter === "all" ? undefined : currentFilter, search || undefined);
  const { data: allData } = useDocuments(1, 1000, undefined);

  const counts: Record<FilterTab, number> | undefined = allData?.documents
    ? {
        all: allData.total,
        pending: allData.documents.filter((d) => d.status === "pending").length,
        processing: allData.documents.filter((d) => d.status === "processing").length,
        processed: allData.documents.filter((d) => d.status === "processed").length,
        failed: allData.documents.filter((d) => d.status === "failed").length,
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

  const handleSearchChange = useCallback((value: string) => {
    setSearch(value);
    setPage(1);
  }, []);

  if (isTenantAdmin) {
    return (
      <div className="animate-fade-up flex h-full flex-col">
        <div className="flex items-center justify-end border-b px-6 py-3" style={{ borderColor: "var(--line)" }}>
          <button
            type="button"
            onClick={() => setUploadOpen(true)}
            className="flex items-center gap-1.5 rounded-md bg-brand-primary px-3 py-1.5 text-sm font-medium text-white"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="size-4">
              <path d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z" />
            </svg>
            Upload documents
          </button>
        </div>

        <div className="flex flex-1 flex-col gap-6 overflow-y-auto p-6">
          <DocumentTable
            data={data}
            isLoading={isLoading}
            page={page}
            perPage={perPage}
            onPageChange={handlePageChange}
            currentFilter={currentFilter}
            onFilterChange={handleFilterChange}
            counts={counts}
            search={search}
            onSearchChange={handleSearchChange}
          />
        </div>

        <UploadDialog open={uploadOpen} onClose={() => setUploadOpen(false)} purpose="training" />
      </div>
    );
  }

  return (
    <div className="animate-fade-up flex h-full flex-col">
      <div className="flex items-center justify-end border-b px-6 py-3" style={{ borderColor: "var(--line)" }}>
        <button
          type="button"
          onClick={() => setUploadOpen(true)}
          className="flex items-center gap-1.5 rounded-md bg-brand-primary px-3 py-1.5 text-sm font-medium text-white"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="size-4">
            <path d="M10.75 4.75a.75.75 0 00-1.5 0v4.5h-4.5a.75.75 0 000 1.5h4.5v4.5a.75.75 0 001.5 0v-4.5h4.5a.75.75 0 000-1.5h-4.5v-4.5z" />
          </svg>
          Upload documents
        </button>
      </div>

      <div className="flex flex-1 flex-col gap-6 overflow-y-auto p-6">
        <DocumentTable
          data={data}
          isLoading={isLoading}
          page={page}
          perPage={perPage}
          onPageChange={handlePageChange}
          currentFilter={currentFilter}
          onFilterChange={handleFilterChange}
          counts={counts}
          search={search}
          onSearchChange={handleSearchChange}
        />
      </div>

      <UploadDialog open={uploadOpen} onClose={() => setUploadOpen(false)} purpose="query" />
    </div>
  );
}
