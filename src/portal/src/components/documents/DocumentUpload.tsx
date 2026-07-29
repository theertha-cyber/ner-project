"use client";

import { useState, useRef, useCallback } from "react";
import { useUpload } from "@/hooks/use-upload";

const ACCEPTED_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/tiff"];
const MAX_SIZE = 50 * 1024 * 1024;
const MAX_BATCH = 20;

type FileStatus = "pending" | "uploading" | "success" | "failed" | "cancelled" | "rejected";

interface BatchItem {
  name: string;
  status: FileStatus;
  error?: string;
}

export function DocumentUpload() {
  const [dragOver, setDragOver] = useState(false);
  const [batch, setBatch] = useState<BatchItem[]>([]);
  const [batchIndex, setBatchIndex] = useState<number | null>(null);
  const [batchError, setBatchError] = useState<string | null>(null);
  const [purpose, setPurpose] = useState<"query" | "training">("query");
  const inputRef = useRef<HTMLInputElement>(null);
  const cancelRequested = useRef(false);
  const { upload, progress, isUploading, reset, cancel } = useUpload();

  const validate = useCallback((file: File): string | null => {
    if (!ACCEPTED_TYPES.includes(file.type)) {
      return `File type "${file.type}" is not supported. Accepted: PDF, JPEG, PNG, TIFF.`;
    }
    if (file.size > MAX_SIZE) {
      return `File exceeds the 50MB limit (${(file.size / (1024 * 1024)).toFixed(1)}MB).`;
    }
    return null;
  }, []);

  const handleFiles = useCallback(
    async (files: File[]) => {
      setBatchError(null);

      if (files.length > MAX_BATCH) {
        setBatch([]);
        setBatchIndex(null);
        setBatchError(`Too many files selected (${files.length}). Upload at most ${MAX_BATCH} files at once.`);
        return;
      }

      reset();
      cancelRequested.current = false;

      const items: BatchItem[] = files.map((file) => {
        const err = validate(file);
        return err
          ? { name: file.name, status: "rejected", error: err }
          : { name: file.name, status: "pending" };
      });
      setBatch(items);

      for (let i = 0; i < files.length; i++) {
        if (items[i].status === "rejected") continue;

        if (cancelRequested.current) {
          setBatch((prev) => {
            const next = [...prev];
            next[i] = { ...next[i], status: "cancelled" };
            return next;
          });
          continue;
        }

        setBatchIndex(i);
        setBatch((prev) => {
          const next = [...prev];
          next[i] = { ...next[i], status: "uploading" };
          return next;
        });

        try {
          await upload(files[i], purpose);
          setBatch((prev) => {
            const next = [...prev];
            next[i] = { ...next[i], status: "success" };
            return next;
          });
        } catch (err) {
          if (cancelRequested.current) {
            setBatch((prev) => {
              const next = [...prev];
              next[i] = { ...next[i], status: "cancelled" };
              return next;
            });
          } else {
            setBatch((prev) => {
              const next = [...prev];
              next[i] = {
                ...next[i],
                status: "failed",
                error: err instanceof Error ? err.message : "Upload failed",
              };
              return next;
            });
          }
        }
      }

      setBatchIndex(null);
    },
    [upload, validate, reset, purpose],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragOver(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setDragOver(false);

      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) handleFiles(files);
    },
    [handleFiles],
  );

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = e.target.files ? Array.from(e.target.files) : [];
      if (files.length > 0) handleFiles(files);
      if (inputRef.current) inputRef.current.value = "";
    },
    [handleFiles],
  );

  const handleClick = useCallback(() => {
    if (!isUploading) inputRef.current?.click();
  }, [isUploading]);

  const handleCancel = useCallback(() => {
    cancelRequested.current = true;
    cancel();
  }, [cancel]);

  const currentItem = batchIndex !== null ? batch[batchIndex] : null;
  const rejectedItems = batch.filter((item) => item.status === "rejected");
  const failedItems = batch.filter((item) => item.status === "failed");
  const cancelledItems = batch.filter((item) => item.status === "cancelled");
  const succeededCount = batch.filter((item) => item.status === "success").length;
  const nonRejectedTotal = batch.length - rejectedItems.length;
  const isBatch = nonRejectedTotal > 1;
  const isBatchDone = nonRejectedTotal > 0 && batchIndex === null;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-4 text-sm" style={{ color: "var(--ink-2)" }}>
        <label className="flex cursor-pointer items-center gap-1.5">
          <input
            type="radio"
            name="upload-purpose"
            value="query"
            checked={purpose === "query"}
            onChange={() => setPurpose("query")}
          />
          Query (chat-searchable)
        </label>
        <label className="flex cursor-pointer items-center gap-1.5">
          <input
            type="radio"
            name="upload-purpose"
            value="training"
            checked={purpose === "training"}
            onChange={() => setPurpose("training")}
          />
          Training (for annotation)
        </label>
      </div>
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") handleClick();
        }}
        className={[
          "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed p-8 transition-colors",
          dragOver
            ? "border-brand-primary bg-brand-primary/5"
            : "hover:border-gray-400",
          isUploading ? "pointer-events-none" : "",
        ].join(" ")}
        style={{
          borderColor: dragOver ? undefined : "var(--line)",
          background: dragOver ? undefined : "var(--surface-3)",
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png,.tiff,.tif"
          multiple
          className="hidden"
          onChange={handleInputChange}
        />

        {isUploading && currentItem ? (
          <div className="flex w-full max-w-xs flex-col items-center gap-2">
            {isBatch && (
              <span className="text-xs" style={{ color: "var(--ink-3)" }}>
                file {batchIndex! + 1} of {nonRejectedTotal}
              </span>
            )}
            <span className="max-w-full truncate text-xs" style={{ color: "var(--ink-3)" }}>
              {currentItem.name}
            </span>
            <div className="h-2 w-full overflow-hidden rounded-full" style={{ background: "var(--surface-3)" }}>
              <div
                className="h-full rounded-full bg-brand-primary transition-all duration-300"
                style={{ width: `${progress}%` }}
              />
            </div>
            <span className="text-sm" style={{ color: "var(--ink-3)" }}>{progress}% uploaded</span>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                handleCancel();
              }}
              className="text-xs underline"
              style={{ color: "var(--ink-3)" }}
            >
              Cancel
            </button>
          </div>
        ) : isBatchDone ? (
          <div className="flex flex-col items-center gap-1">
            <div className="flex items-center gap-2" style={{ color: "var(--color-success)" }}>
              <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="size-5">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.857-9.809a.75.75 0 00-1.214-.882l-3.483 4.79-1.88-1.88a.75.75 0 10-1.06 1.061l2.5 2.5a.75.75 0 001.137-.089l4-5.5z" clipRule="evenodd" />
              </svg>
              <span className="text-sm font-medium">
                {isBatch || succeededCount !== 1
                  ? `${succeededCount} of ${nonRejectedTotal} uploaded successfully`
                  : "Upload successful"}
              </span>
            </div>
            {(failedItems.length > 0 || cancelledItems.length > 0) && (
              <div className="mt-1 flex flex-col gap-0.5 text-xs" style={{ color: "var(--bad)" }} role="alert">
                {failedItems.map((item) => (
                  <span key={item.name}>{item.name}: {item.error ?? "failed"}</span>
                ))}
                {cancelledItems.map((item) => (
                  <span key={item.name}>{item.name}: cancelled</span>
                ))}
              </div>
            )}
          </div>
        ) : (
          <>
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20" fill="currentColor" className="mb-2 size-8" style={{ color: "var(--ink-3)" }}>
              <path d="M9.25 13.25a.75.75 0 001.5 0V4.636l2.955 3.128a.75.75 0 001.09-1.03l-4.25-4.5a.75.75 0 00-1.09 0l-4.25 4.5a.75.75 0 101.09 1.03L9.25 4.636V13.25z" />
              <path d="M3.5 12.75a.75.75 0 00-1.5 0v2.5A2.75 2.75 0 004.75 18h10.5A2.75 2.75 0 0018 15.25v-2.5a.75.75 0 00-1.5 0v2.5c0 .69-.56 1.25-1.25 1.25H4.75c-.69 0-1.25-.56-1.25-1.25v-2.5z" />
            </svg>
            <p className="text-sm" style={{ color: "var(--ink-2)" }}>
              <span className="font-medium text-brand-primary">Click to upload</span> or drag and drop
            </p>
            <p className="mt-1 text-xs" style={{ color: "var(--ink-3)" }}>
              PDF, JPEG, PNG, or TIFF (max 50MB, up to {MAX_BATCH} files)
            </p>
          </>
        )}
      </div>

      {batchError && (
        <p className="text-sm" style={{ color: "var(--bad)" }} role="alert">
          {batchError}
        </p>
      )}

      {rejectedItems.length > 0 && (
        <div className="flex flex-col gap-0.5" role="alert">
          {rejectedItems.map((item) => (
            <p key={item.name} className="text-sm" style={{ color: "var(--bad)" }}>
              {item.name}: {item.error}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
