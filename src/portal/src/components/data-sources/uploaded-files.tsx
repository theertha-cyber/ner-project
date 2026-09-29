"use client";

import { useRef, useState } from "react";
import {
  useTabularDelete,
  useTabularFiles,
  useTabularUpload,
  type SafeApiHttpError,
} from "@/hooks/use-data-sources";
import {
  TABULAR_ACCEPTED_EXTENSIONS,
  TABULAR_FAILURE_LABELS,
  TABULAR_MAX_FILE_MB,
  TABULAR_MAX_FILES,
  TABULAR_STATUS_LABELS,
  tabularErrorMessage,
  tabularExtensionAllowed,
  type DataPlaneMode,
  type TabularFile,
} from "@/lib/data-sources";
import { FileReview } from "./file-review";

/**
 * "Uploaded files" on `/settings/data-sources` (ADR-018, ADR-019): tenant-admin
 * CSV/XLSX uploads that chat can answer exact questions from once published.
 * Separate from the connection collection; shows served and pending versions,
 * status labels, the upload control with its limits, and fixed error messages.
 */
export function UploadedFilesSection({ dataPlaneMode }: { dataPlaneMode: DataPlaneMode }) {
  const { data, isLoading, isError, refetch } = useTabularFiles();
  const upload = useTabularUpload();
  const remove = useTabularDelete();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [reviewing, setReviewing] = useState<{ fileId: string; version: number } | null>(null);
  const [confirming, setConfirming] = useState<TabularFile | null>(null);
  const [replacing, setReplacing] = useState<string | null>(null);

  if (data && !data.enabled) return null;

  function pick(fileId: string | null) {
    setUploadError(null);
    setReplacing(fileId);
    inputRef.current?.click();
  }

  function onFileChosen(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (!tabularExtensionAllowed(file.name)) {
      setUploadError(tabularErrorMessage("UNSUPPORTED_FILE_TYPE"));
      return;
    }
    if (file.size > TABULAR_MAX_FILE_MB * 1024 * 1024) {
      setUploadError(tabularErrorMessage("FILE_TOO_LARGE"));
      return;
    }
    upload.mutate(
      { file, fileId: replacing ?? undefined },
      { onError: (err) => setUploadError(tabularErrorMessage((err as SafeApiHttpError).code ?? "INTERNAL_ERROR")) },
    );
  }

  const files = data?.files ?? [];

  if (reviewing) {
    return (
      <section aria-labelledby="uploaded-files-heading" className="flex flex-col gap-4">
        <h2 id="uploaded-files-heading" className="text-lg font-semibold" style={{ color: "var(--ink)" }}>
          Uploaded files
        </h2>
        <FileReview
          fileId={reviewing.fileId}
          version={reviewing.version}
          onClose={() => setReviewing(null)}
          onPublished={() => {
            setReviewing(null);
            refetch();
          }}
        />
      </section>
    );
  }

  return (
    <section aria-labelledby="uploaded-files-heading" className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 id="uploaded-files-heading" className="text-lg font-semibold" style={{ color: "var(--ink)" }}>
            Uploaded files
          </h2>
          <p className="mt-1 max-w-[70ch] text-sm leading-6" style={{ color: "var(--ink-2)" }}>
            Upload spreadsheets for exact answers in chat — totals, counts, filters and rankings. Accepts{" "}
            {TABULAR_ACCEPTED_EXTENSIONS.join(" and ")} only, up to {TABULAR_MAX_FILE_MB} MB and 1,000,000 rows per file,
            and {TABULAR_MAX_FILES} files per tenant. Nothing reaches chat until you review and publish it.
          </p>
          {dataPlaneMode === "tenant_owned" && (
            <p data-testid="tabular-residency-notice" className="mt-2 max-w-[70ch] text-sm leading-6" style={{ color: "var(--ink-2)" }}>
              Your tenant keeps its data in its own database, but uploaded files are the exception: the original file and
              its query copy are stored in the platform&apos;s object storage, not in your infrastructure. Do not upload
              files that must stay in your own environment.
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => pick(null)}
          disabled={upload.isPending}
          className="rounded-md px-4 py-2 text-sm font-semibold outline-none focus-visible:ring-2 disabled:opacity-60"
          style={{ background: "var(--primary)", color: "#fff" }}
        >
          {upload.isPending ? "Uploading…" : "Upload file"}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept={TABULAR_ACCEPTED_EXTENSIONS.join(",")}
          aria-label="Choose a spreadsheet to upload"
          className="hidden"
          onChange={onFileChosen}
        />
      </div>

      {uploadError && (
        <p role="alert" className="rounded-md border p-3 text-sm" style={{ borderColor: "var(--line)", color: "var(--ink)" }}>
          {uploadError}
        </p>
      )}

      {isLoading && (
        <p role="status" className="text-sm" style={{ color: "var(--ink-2)" }}>
          Loading uploaded files…
        </p>
      )}

      {isError && (
        <p role="status" className="text-sm" style={{ color: "var(--ink-2)" }}>
          Uploaded files could not be loaded.{" "}
          <button type="button" className="underline" onClick={() => refetch()}>
            Retry
          </button>
        </p>
      )}

      {!isLoading && !isError && files.length === 0 && (
        <p className="rounded-md border p-6 text-center text-sm" style={{ borderColor: "var(--line)", color: "var(--ink-2)" }}>
          No uploaded files yet.
        </p>
      )}

      {files.length > 0 && (
        <ul aria-label="Uploaded files" className="flex flex-col gap-2">
          {files.map((file) => (
            <FileEntry
              key={file.id}
              file={file}
              onReview={(version) => setReviewing({ fileId: file.id, version })}
              onNewVersion={() => pick(file.id)}
              onDelete={() => setConfirming(file)}
            />
          ))}
        </ul>
      )}

      {confirming && (
        <div role="dialog" aria-modal="true" aria-labelledby="tabular-delete-title" className="rounded-md border p-4 shadow-card" style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}>
          <p id="tabular-delete-title" className="text-sm font-semibold" style={{ color: "var(--ink)" }}>
            Delete {confirming.display_name}?
          </p>
          <p className="mt-1 text-sm" style={{ color: "var(--ink-2)" }}>
            Chat will stop using {confirming.display_name} immediately, and every stored version of it is removed.
          </p>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              className="rounded-md px-3 py-1.5 text-sm font-semibold"
              style={{ background: "var(--danger, #b42318)", color: "#fff" }}
              onClick={() => {
                const target = confirming;
                setConfirming(null);
                remove.mutate({ fileId: target.id });
              }}
            >
              Delete file
            </button>
            <button type="button" className="rounded-md border px-3 py-1.5 text-sm" style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--ink)" }} onClick={() => setConfirming(null)}>
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function FileEntry({
  file,
  onReview,
  onNewVersion,
  onDelete,
}: {
  file: TabularFile;
  onReview: (version: number) => void;
  onNewVersion: () => void;
  onDelete: () => void;
}) {
  const pending = file.pending;
  const reviewable = pending && pending.status === "needs_review" ? pending.version : null;
  return (
    <li
      data-testid={`tabular-file-${file.id}`}
      className="flex flex-wrap items-center justify-between gap-3 rounded-md border p-3"
      style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}
    >
      <div className="flex flex-col gap-1">
        <span className="text-sm font-semibold" style={{ color: "var(--ink)" }}>
          {file.display_name}
        </span>
        <span className="text-xs" style={{ color: "var(--ink-2)" }}>
          {file.served_version !== null ? (
            <>
              <StatusChip status="ready" /> v{file.served_version} served
            </>
          ) : (
            <StatusChip status={pending?.status ?? file.status} />
          )}
          {pending && file.served_version !== null && (
            <>
              {" · "}v{pending.version} pending: <StatusChip status={pending.status} />
            </>
          )}
          {pending && file.served_version === null && <> · v{pending.version}</>}
          {file.row_count !== null && <> · {file.row_count.toLocaleString()} rows</>}
          {" · updated "}
          {new Date(file.updated_at).toLocaleString()}
        </span>
        {pending?.status === "failed" && (
          <span className="text-xs" style={{ color: "var(--ink-2)" }}>
            {TABULAR_FAILURE_LABELS[pending.failure_reason ?? "INTERNAL_ERROR"] ?? TABULAR_FAILURE_LABELS.INTERNAL_ERROR}
          </span>
        )}
      </div>
      <div className="flex gap-2">
        {reviewable !== null && (
          <button type="button" className="rounded-md border px-3 py-1.5 text-sm font-medium" style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--ink)" }} onClick={() => onReview(reviewable)}>
            Review v{reviewable}
          </button>
        )}
        <button type="button" className="rounded-md border px-3 py-1.5 text-sm font-medium" style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--ink)" }} onClick={onNewVersion}>
          Upload new version
        </button>
        <button type="button" className="rounded-md border px-3 py-1.5 text-sm font-medium" style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--ink)" }} onClick={onDelete} aria-label={`Delete ${file.display_name}`}>
          Delete
        </button>
      </div>
    </li>
  );
}

function StatusChip({ status }: { status: string }) {
  return (
    <span className="rounded px-1.5 py-0.5 text-xs font-medium" style={{ background: "var(--surface-3, #eef)", color: "var(--ink)" }}>
      {TABULAR_STATUS_LABELS[status] ?? status}
    </span>
  );
}
