"use client";

import { Badge } from "@/components/ui";
import type { BadgeVariant } from "@/components/ui";
import type { Document, DocumentStatus } from "@/types/documents";

const statusToVariant: Record<DocumentStatus, BadgeVariant> = {
  pending: "pending_approval",
  processing: "running",
  processed: "completed",
  failed: "failed",
  deleted: "cancelled",
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

const mimeLabel: Record<string, string> = {
  "application/pdf": "PDF",
  "image/jpeg": "JPEG",
  "image/png": "PNG",
  "image/tiff": "TIFF",
};

function contentTypeLabel(ct: string): string {
  return mimeLabel[ct] ?? ct.split("/").pop()?.toUpperCase() ?? ct;
}

export interface DocumentRowProps {
  doc: Document;
  onDelete: (id: string) => void;
  isDeleting?: boolean;
  isRemoving?: boolean;
}

export function DocumentRow({ doc, onDelete, isDeleting, isRemoving }: DocumentRowProps) {
  const handleDelete = () => {
    if (!isDeleting) onDelete(doc.id);
  };

  return (
    <tr
      className={[
        "border-b border-gray-100 transition-all duration-300",
        isDeleting ? "opacity-50" : "",
        isRemoving ? "translate-x-full opacity-0" : "",
      ].join(" ")}
    >
      <td className="px-4 py-3 text-sm text-gray-900">{doc.filename}</td>
      <td className="px-4 py-3 text-sm text-gray-500">{contentTypeLabel(doc.content_type)}</td>
      <td className="px-4 py-3 text-sm text-gray-500">{formatFileSize(doc.file_size)}</td>
      <td className="px-4 py-3 text-sm">
        <span className="inline-flex items-center gap-1.5">
          {doc.status === "processing" && (
            <span className="inline-block size-1.5 animate-pulse rounded-full bg-blue-500" />
          )}
          <Badge variant={statusToVariant[doc.status]} label={doc.status} />
        </span>
      </td>
      <td className="px-4 py-3 text-sm text-gray-500">{formatDate(doc.created_at)}</td>
      <td className="px-4 py-3 text-sm">
        <button
          type="button"
          onClick={handleDelete}
          disabled={isDeleting}
          className="text-gray-400 hover:text-red-600 disabled:opacity-30"
          aria-label={`Delete ${doc.filename}`}
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="size-4">
            <path fillRule="evenodd" d="M8.75 1A2.75 2.75 0 006 3.75v.443c-.795.077-1.584.176-2.365.298a.75.75 0 10.23 1.482l.149-.022.841 10.518A2.75 2.75 0 007.596 19h4.807a2.75 2.75 0 002.742-2.53l.841-10.52.149.023a.75.75 0 00.23-1.482A41.03 41.03 0 0014 4.193V3.75A2.75 2.75 0 0011.25 1h-2.5zM10 4c.84 0 1.673.025 2.5.075V3.75c0-.69-.56-1.25-1.25-1.25h-2.5c-.69 0-1.25.56-1.25 1.25v.325C8.327 4.025 9.16 4 10 4zM8.58 7.72a.75.75 0 00-1.5.06l.3 7.5a.75.75 0 101.5-.06l-.3-7.5zm4.34.06a.75.75 0 10-1.5-.06l-.3 7.5a.75.75 0 101.5.06l.3-7.5z" clipRule="evenodd" />
          </svg>
        </button>
      </td>
    </tr>
  );
}
