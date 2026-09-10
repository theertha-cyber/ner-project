"use client";

import { useRef, useState } from "react";
import { SafeApiHttpError } from "@/hooks/use-data-sources";
import type { ContractDraft, ContractHistory } from "@/lib/data-sources";
import { Pagination } from "./collection";
import { SafeOutcomeNotice } from "./status";

const MAX_CONTRACT_BYTES = 256 * 1024;

function readFileText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ""));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(file);
  });
}

/* CMP-10 — Schema Contract Upload */

export function ContractUpload({
  pending,
  error,
  result,
  onUpload,
}: {
  pending: boolean;
  error: SafeApiHttpError | null;
  result: ContractDraft | null;
  onUpload: (document: unknown) => void;
}) {
  const [fileName, setFileName] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  async function handleFile(file: File | undefined) {
    setLocalError(null);
    if (!file) return;
    setFileName(file.name);
    if (file.size > MAX_CONTRACT_BYTES) {
      setLocalError(`Contract file exceeds the ${MAX_CONTRACT_BYTES / 1024} KB limit. Split the contract and try again.`);
      return;
    }
    let text: string;
    try {
      text = await readFileText(file);
    } catch {
      setLocalError("The selected file could not be read. Choose a JSON contract and try again — nothing was uploaded.");
      return;
    }
    let document: unknown;
    try {
      document = JSON.parse(text);
    } catch {
      setLocalError("The selected file is not valid JSON. Choose a JSON contract and try again — nothing was uploaded.");
      return;
    }
    if (typeof document !== "object" || document === null || Array.isArray(document)) {
      setLocalError("A schema contract must be a JSON object with a version. Nothing was uploaded.");
      return;
    }
    onUpload(document);
  }

  return (
    <section aria-label="Upload replacement contract" className="rounded-md border p-4" style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}>
      <h2 className="text-base font-semibold" style={{ color: "var(--ink)" }}>
        Upload replacement contract
      </h2>
      <div className="mt-3 flex flex-col gap-2">
        <label htmlFor="contract-file" className="text-sm font-medium tracking-[0.02em]" style={{ color: "var(--ink)" }}>
          Choose JSON file
        </label>
        <input
          ref={inputRef}
          id="contract-file"
          type="file"
          accept="application/json,.json"
          disabled={pending}
          aria-describedby="contract-file-hint"
          onChange={(e) => void handleFile(e.target.files?.[0])}
          className="text-sm outline-none focus-visible:ring-2"
          style={{ color: "var(--ink)" }}
        />
        <span id="contract-file-hint" className="text-xs" style={{ color: "var(--ink-2)" }}>
          JSON object, up to {MAX_CONTRACT_BYTES / 1024} KB. The form state is preserved when validation fails.
        </span>
        {fileName && (
          <p className="text-xs" style={{ color: "var(--ink-2)" }} role="status">
            Selected: {fileName}
          </p>
        )}
      </div>
      {localError && (
        <div className="mt-3" role="alert">
          <SafeOutcomeNotice variant="error" title="File unreadable">
            {localError}
          </SafeOutcomeNotice>
        </div>
      )}
      {error && (
        <div className="mt-3" role="alert" aria-label="Contract validation result">
          <SafeOutcomeNotice variant="error" title={error.code === "INVALID_CONTRACT" ? "Contract invalid" : "Upload failed"} code={error.code} requestId={error.requestId}>
            {error.fieldErrors && error.fieldErrors.length > 0 ? (
              <ul className="mt-1 list-disc pl-5">
                {error.fieldErrors.map((fe, i) => (
                  <li key={`${fe.field}-${i}`}>
                    {fe.field === "version" ? (
                      <a href="#contract-file" className="font-mono underline" onClick={() => inputRef.current?.focus()}>
                        {fe.field}
                      </a>
                    ) : (
                      <span className="font-mono">{fe.field}</span>
                    )}
                    {`: ${fe.message}`}
                  </li>
                ))}
              </ul>
            ) : (
              "Nothing was uploaded. The form state is preserved — correct the file and try again."
            )}
          </SafeOutcomeNotice>
        </div>
      )}
      {result && !error && (
        <div className="mt-3" role="status" aria-label="Contract validation result">
          <SafeOutcomeNotice variant="success" title={`Valid draft version ${result.version}`} code="CONTRACT_VALIDATED">
            Fingerprint <span className="font-mono">{result.fingerprint.slice(0, 12)}…</span>. Publish it from the history below.
          </SafeOutcomeNotice>
        </div>
      )}
    </section>
  );
}

/* CMP-10 — Schema Contract History */

export function ContractHistoryTable({
  history,
  connectionActive,
  publishingVersion,
  publishError,
  onPage,
  onPublish,
}: {
  history: ContractHistory | undefined;
  connectionActive: boolean;
  publishingVersion: number | null;
  publishError: SafeApiHttpError | null;
  onPage: (page: number) => void;
  onPublish: (version: number) => void;
}) {
  const items = history?.items ?? [];
  return (
    <section aria-label="Contract history" className="rounded-md border p-4" style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}>
      <h2 className="text-base font-semibold" style={{ color: "var(--ink)" }}>
        Contract history
      </h2>
      {items.length === 0 ? (
        <div className="mt-3 rounded-md border p-6 text-center" style={{ borderColor: "var(--line-2)", background: "var(--surface-3)" }}>
          <p className="text-sm font-semibold" style={{ color: "var(--ink)" }}>
            No published contract yet
          </p>
          <p className="mt-1 text-sm" style={{ color: "var(--ink-2)" }}>
            Upload a JSON schema contract above to create the first validated draft.
          </p>
        </div>
      ) : (
        <div className="mt-3 overflow-x-auto">
          <table className="w-full border-collapse text-left text-sm">
            <caption className="sr-only">Versioned schema contracts</caption>
            <thead>
              <tr style={{ background: "var(--surface-3)" }}>
                {["Version", "State", "Validation", "Actions"].map((h) => (
                  <th key={h} scope="col" className="px-4 py-3 text-xs font-semibold tracking-[0.06em] uppercase" style={{ color: "var(--ink-2)" }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.version} className="border-t" style={{ borderColor: "var(--line-2)" }}>
                  <td className="px-4 py-3 font-mono font-medium" style={{ color: "var(--ink)" }}>
                    v{item.version}
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--ink)" }}>
                    {item.published ? "Published" : "Valid draft"}
                  </td>
                  <td className="px-4 py-3" style={{ color: "var(--ink-2)" }}>
                    {item.validation_reason && item.validation_reason !== "none" ? item.validation_reason : "Valid"}
                  </td>
                  <td className="px-4 py-3">
                    {!item.published && (
                      <button
                        type="button"
                        disabled={!connectionActive || publishingVersion !== null}
                        onClick={() => onPublish(item.version)}
                        aria-describedby={!connectionActive ? "publish-hint" : undefined}
                        className="rounded-md border px-3 py-1.5 text-sm font-medium outline-none focus-visible:ring-2 disabled:opacity-50"
                        style={{ borderColor: "var(--primary)", background: "var(--surface-2)", color: "var(--primary-2)" }}
                      >
                        {publishingVersion === item.version ? "Publishing…" : "Publish validated version"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {!connectionActive && items.length > 0 && (
        <p id="publish-hint" className="mt-2 text-xs" style={{ color: "var(--ink-2)" }}>
          Publishing requires an active connection. Activate it from the connection detail screen.
        </p>
      )}
      {publishError && (
        <div className="mt-3">
          <SafeOutcomeNotice variant="error" title="Publish failed" code={publishError.code} requestId={publishError.requestId} />
        </div>
      )}
      {history && history.total > 0 && (
        <div className="mt-3">
          <Pagination page={history.page} pageSize={history.page_size} total={history.total} totalPages={history.total_pages} onPage={onPage} />
        </div>
      )}
    </section>
  );
}
