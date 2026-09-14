"use client";

import { useState, useRef, useCallback } from "react";
import { useUpload } from "@/hooks/use-upload";
import { usePrelabelTrigger } from "@/hooks/use-prelabel-trigger";
import { useEntityTypes } from "@/hooks/use-entity-types";

const ACCEPTED_TYPES = ["application/pdf", "image/jpeg", "image/png", "image/tiff"];
// Q&A-pair guidance documents are text, not scanned pages, so they accept the office text
// formats a team is likely to have written one in. The browser reports .txt as text/plain
// and .docx as this vendor type (or, on some systems, an empty string — the extension check
// below is the backstop).
const QA_PAIR_ACCEPTED_TYPES = [
  "application/pdf",
  "text/plain",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];
const QA_PAIR_ACCEPTED_EXTENSIONS = [".pdf", ".txt", ".docx"];
const MAX_SIZE = 50 * 1024 * 1024;
const MAX_BATCH = 20;

type FileStatus = "pending" | "uploading" | "success" | "failed" | "cancelled" | "rejected";

type AnnotationMode = "manual" | "automated";

interface BatchItem {
  name: string;
  status: FileStatus;
  error?: string;
  /** Set once the upload succeeds; the pre-label trigger loop addresses documents by this. */
  docId?: string;
}

/**
 * Pre-label trigger outcome, held separately from `BatchItem.status`. Upload and pre-labeling
 * are independent concerns: a document that uploaded fine but failed to queue is still a
 * successful upload, and writing a trigger failure into the upload status would make an LLM
 * outage look like an ingestion outage.
 */
interface TriggerFailure {
  name: string;
  error: string;
}

interface DocumentUploadProps {
  /**
   * Fixed upload purpose. Chosen by the caller from the signed-in role and the chosen
   * action, not typed by the uploader: tenant admins upload for annotation or as a
   * Q&A pair, business users for query only.
   */
  purpose?: "query" | "training" | "qa_pair";
  /**
   * Seeds the initial radio selection only — e.g. the Automated flow's own "Upload
   * documents" hand-off lands here with Automated already selected, so the tenant admin
   * doesn't have to remember to flip it. The per-batch reset to Manual (annotationMode
   * persisting would silently send a later, unrelated batch through Automated by accident)
   * is unaffected: it always resets to Manual, never back to this default.
   */
  defaultAnnotationMode?: AnnotationMode;
}

export function DocumentUpload({ purpose = "query", defaultAnnotationMode = "manual" }: DocumentUploadProps) {
  const isQaPair = purpose === "qa_pair";
  const [dragOver, setDragOver] = useState(false);
  const [batch, setBatch] = useState<BatchItem[]>([]);
  const [batchIndex, setBatchIndex] = useState<number | null>(null);
  const [batchError, setBatchError] = useState<string | null>(null);
  const [annotationMode, setAnnotationMode] = useState<AnnotationMode>(defaultAnnotationMode);
  // The batch reports against the mode it actually ran under, not the live selector, which
  // resets to Manual the moment the batch finishes.
  const [batchMode, setBatchMode] = useState<AnnotationMode>("manual");
  const [triggerIndex, setTriggerIndex] = useState<number | null>(null);
  const [triggerTotal, setTriggerTotal] = useState(0);
  const [queuedCount, setQueuedCount] = useState(0);
  const [triggerFailures, setTriggerFailures] = useState<TriggerFailure[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const cancelRequested = useRef(false);
  const { upload, progress, isUploading, reset, cancel } = useUpload();
  const { trigger } = usePrelabelTrigger();
  const { data: entityTypesData } = useEntityTypes();

  // Informational only — Automated mode stays selectable with zero active entity types.
  // Forcing Manual here used to push tenant admins into creating a throwaway "sample" entity
  // type just to unlock the radio, and that placeholder then shows up in the Suggest Entity
  // Types prompt as "already configured, do not propose again" (schema_proposal.py
  // `build_existing_config_block`), quietly suppressing the real type the LLM would otherwise
  // have proposed. The per-document trigger already degrades gracefully when there is nothing
  // to extract against — see `usePrelabelTrigger`'s per-file failure handling below — so upload
  // itself was never actually blocked; only the toggle was.
  const activeEntityTypeCount = (entityTypesData?.entity_types ?? []).filter(
    (et) => et.is_active,
  ).length;
  const automatedHasNoActiveTypes = activeEntityTypeCount === 0;

  const validate = useCallback((file: File): string | null => {
    if (isQaPair) {
      const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
      const okType = QA_PAIR_ACCEPTED_TYPES.includes(file.type);
      const okExt = QA_PAIR_ACCEPTED_EXTENSIONS.includes(ext);
      if (!okType && !okExt) {
        return `File type "${file.type || ext || "unknown"}" is not supported. Accepted: PDF, TXT, DOCX.`;
      }
    } else if (!ACCEPTED_TYPES.includes(file.type)) {
      return `File type "${file.type}" is not supported. Accepted: PDF, JPEG, PNG, TIFF.`;
    }
    if (file.size > MAX_SIZE) {
      return `File exceeds the 50MB limit (${(file.size / (1024 * 1024)).toFixed(1)}MB).`;
    }
    return null;
  }, [isQaPair]);

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

      const modeForBatch: AnnotationMode = annotationMode;
      setBatchMode(modeForBatch);
      setTriggerIndex(null);
      setTriggerTotal(0);
      setQueuedCount(0);
      setTriggerFailures([]);

      const items: BatchItem[] = files.map((file) => {
        const err = validate(file);
        return err
          ? { name: file.name, status: "rejected", error: err }
          : { name: file.name, status: "pending" };
      });
      setBatch(items);

      // Only successfully uploaded documents land here — rejected files `continue` before the
      // upload call and failures never reach the push — so the trigger loop below is already
      // filtered by construction.
      const uploaded: { index: number; name: string; docId: string }[] = [];

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
          const result = await upload(files[i], purpose);
          const docId = result?.id ?? "";
          // A response without an id cannot be addressed by the per-document pre-label
          // endpoint, so there is nothing to queue — the upload itself still succeeded.
          if (docId) uploaded.push({ index: i, name: files[i].name, docId });
          setBatch((prev) => {
            const next = [...prev];
            next[i] = { ...next[i], status: "success", docId };
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

      // A distinct second pass, entered only after the upload loop has exited. Sequential
      // awaits, never `Promise.all` — a browser firing N concurrent POSTs has no backpressure
      // and produces partial failures that are hard to report.
      if (modeForBatch === "automated" && uploaded.length > 0) {
        setTriggerTotal(uploaded.length);
        const failures: TriggerFailure[] = [];
        let queued = 0;

        for (let i = 0; i < uploaded.length; i++) {
          setTriggerIndex(i);
          try {
            await trigger(uploaded[i].docId);
            queued += 1;
          } catch (err) {
            // Recorded, never rethrown and never `break`: one document failing to queue must
            // not deny the rest, and must not touch the upload item's status.
            failures.push({
              name: uploaded[i].name,
              error: err instanceof Error ? err.message : "Failed to queue for pre-labeling",
            });
          }
        }

        setQueuedCount(queued);
        setTriggerFailures(failures);
        setTriggerIndex(null);
      }

      // Automated is opt-in per batch: a mode that persisted would silently send later
      // batches to an external LLM.
      setAnnotationMode("manual");
    },
    [upload, validate, reset, purpose, annotationMode, trigger],
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
  const isTriggering = triggerIndex !== null;
  const isBatchDone = nonRejectedTotal > 0 && batchIndex === null && !isTriggering;

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm" style={{ color: "var(--ink-2)" }}>
        {isQaPair
          ? "This question/answer document guides which entity types are proposed during schema suggestion. It is not annotated or chat-searchable."
          : purpose === "training"
          ? "These documents are uploaded for annotation."
          : "These documents are uploaded for querying (chat-searchable)."}
      </p>

      {/* Annotation mode — training uploads only. Query documents are never annotated, so the
          control would be a dead one there. Same `purpose` branch as the copy above. */}
      {purpose === "training" && (
        <fieldset className="flex flex-col gap-1.5" disabled={isUploading || isTriggering}>
          <legend className="text-xs font-medium uppercase tracking-wide" style={{ color: "var(--ink-3)" }}>
            Annotation mode
          </legend>
          <div className="flex gap-4">
            <label className="flex items-center gap-1.5 text-sm" style={{ color: "var(--ink-2)" }}>
              <input
                type="radio"
                name="annotation-mode"
                value="manual"
                checked={annotationMode === "manual"}
                onChange={() => setAnnotationMode("manual")}
              />
              Manual
            </label>
            <label className="flex items-center gap-1.5 text-sm" style={{ color: "var(--ink-2)" }}>
              <input
                type="radio"
                name="annotation-mode"
                value="automated"
                checked={annotationMode === "automated"}
                onChange={() => setAnnotationMode("automated")}
              />
              Automated
            </label>
          </div>
          {annotationMode === "automated" && automatedHasNoActiveTypes && (
            <p className="text-xs" style={{ color: "var(--ink-3)" }}>
              No entity types are active yet, so pre-labeling won&apos;t find anything to extract
              until you approve some — the upload itself will still go through.
            </p>
          )}
        </fieldset>
      )}

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
          accept={isQaPair ? ".pdf,.txt,.docx" : ".pdf,.jpg,.jpeg,.png,.tiff,.tif"}
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
        ) : isTriggering ? (
          <div className="flex w-full max-w-xs flex-col items-center gap-2">
            <span className="text-sm" style={{ color: "var(--ink-3)" }}>
              Queueing {triggerIndex! + 1} of {triggerTotal} for pre-labeling
            </span>
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
            {batchMode === "automated" && (
              <div className="mt-0.5 flex flex-col items-center gap-0.5 text-xs" style={{ color: "var(--ink-3)" }}>
                <span>{queuedCount} queued for pre-labeling</span>
                {triggerFailures.length > 0 && (
                  <>
                    <span>{triggerFailures.length} failed to queue for pre-labeling</span>
                    {triggerFailures.map((failure) => (
                      <span key={failure.name}>
                        {failure.name}: {failure.error}
                      </span>
                    ))}
                  </>
                )}
              </div>
            )}
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
              {isQaPair
                ? `PDF, TXT, or DOCX (max 50MB, up to ${MAX_BATCH} files)`
                : `PDF, JPEG, PNG, or TIFF (max 50MB, up to ${MAX_BATCH} files)`}
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
