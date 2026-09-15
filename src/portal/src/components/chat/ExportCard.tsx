"use client";

import { useState } from "react";
import { FileSpreadsheet, Download, Loader2 } from "lucide-react";
import { authFetch } from "@/lib/auth-fetch";

export interface ExportAvailability {
  message_id: string;
  row_count: number;
  formats: string[];
}

interface ExportCardProps {
  export_: ExportAvailability;
}

async function downloadExport(messageId: string, format: "csv" | "xlsx") {
  const resp = await authFetch(`/api/v1/chat/messages/${messageId}/export?format=${format}`);
  if (!resp.ok) throw new Error(`Export request failed with status ${resp.status}`);

  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  try {
    const link = document.createElement("a");
    link.href = url;
    link.download = `chat-export-${messageId}.${format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  } finally {
    URL.revokeObjectURL(url);
  }
}

export function ExportCard({ export_ }: ExportCardProps) {
  const [pending, setPending] = useState<"csv" | "xlsx" | null>(null);
  const [error, setError] = useState(false);

  const handleDownload = async (format: "csv" | "xlsx") => {
    setPending(format);
    setError(false);
    try {
      await downloadExport(export_.message_id, format);
    } catch {
      setError(true);
    } finally {
      setPending(null);
    }
  };

  return (
    <div
      style={{
        marginTop: 10,
        display: "flex",
        alignItems: "center",
        gap: 10,
        padding: "10px 14px",
        borderRadius: 10,
        border: "1px solid var(--line)",
        background: "var(--surface-2)",
        maxWidth: 360,
      }}
    >
      <FileSpreadsheet size={20} color="var(--ink-3)" style={{ flexShrink: 0 }} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, color: "var(--ink)", fontWeight: 500 }}>
          {export_.row_count} results
        </div>
        <div style={{ fontSize: 12, color: "var(--ink-3)" }}>
          Download the full result
        </div>
      </div>
      <div style={{ display: "flex", gap: 6 }}>
        {export_.formats.includes("csv") && (
          <button
            type="button"
            onClick={() => handleDownload("csv")}
            disabled={pending !== null}
            aria-label="Download CSV"
            title="Download CSV"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "5px 10px",
              fontSize: 12,
              border: "1px solid var(--line)",
              borderRadius: 6,
              background: "var(--surface)",
              color: "var(--ink-2)",
              cursor: pending === null ? "pointer" : "default",
            }}
          >
            {pending === "csv" ? <Loader2 size={13} /> : <Download size={13} />}
            CSV
          </button>
        )}
        {export_.formats.includes("xlsx") && (
          <button
            type="button"
            onClick={() => handleDownload("xlsx")}
            disabled={pending !== null}
            aria-label="Download XLSX"
            title="Download XLSX"
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 4,
              padding: "5px 10px",
              fontSize: 12,
              border: "1px solid var(--line)",
              borderRadius: 6,
              background: "var(--surface)",
              color: "var(--ink-2)",
              cursor: pending === null ? "pointer" : "default",
            }}
          >
            {pending === "xlsx" ? <Loader2 size={13} /> : <Download size={13} />}
            XLSX
          </button>
        )}
      </div>
      {error && (
        <span style={{ fontSize: 11, color: "var(--bad)" }}>Download failed</span>
      )}
    </div>
  );
}
