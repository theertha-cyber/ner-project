"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { useFocusTrap } from "@/hooks/use-focus-trap";
import { ProviderConfigForm, type ConfigPayload } from "./lifecycle";
import { PROVIDER_LABELS, TENANT_OWNED_ONLY_PROVIDERS, type ConnectionProvider } from "@/lib/data-sources";
import type { SafeApiHttpError } from "@/hooks/use-data-sources";

export interface CreateConnectionModalProps {
  open: boolean;
  onClose: () => void;
  submitting: boolean;
  serverError: SafeApiHttpError | null;
  onSubmit: (payload: ConfigPayload) => void;
  /** `tenant_owned` unlocks the data-plane provider option (task 13.1); a
   * `platform` tenant (the default, and the value if the caller hasn't loaded
   * data-plane status yet) never sees it. */
  dataPlaneMode?: "platform" | "tenant_owned";
}

export function CreateConnectionModal({
  open,
  onClose,
  submitting,
  serverError,
  onSubmit,
  dataPlaneMode = "platform",
}: CreateConnectionModalProps) {
  const { panelRef } = useFocusTrap({ open, onClose });
  const [mounted, setMounted] = useState(false);
  const [provider, setProvider] = useState<ConnectionProvider>("azure_blob");

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (open) setProvider("azure_blob");
  }, [open]);

  if (!mounted || !open) return null;

  return createPortal(
    <>
      <div className="fixed inset-0 z-40 bg-black/40" onClick={onClose} aria-hidden="true" />

      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label="Create connection"
        className="fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 rounded-md p-6 shadow-overlay"
        style={{ background: "var(--surface-2)", transform: "translate(-50%, -50%)" }}
      >
        <div className="mb-4 flex items-start justify-between gap-3">
          <h2 className="text-lg font-semibold" style={{ color: "var(--ink)" }}>
            New connection
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-sm text-sm font-medium underline outline-none focus-visible:ring-2"
            style={{ color: "var(--ink-2)" }}
          >
            Cancel
          </button>
        </div>

        <div className="mb-4 flex flex-col gap-1">
          <label htmlFor="create-provider" className="text-sm font-medium tracking-[0.02em]" style={{ color: "var(--ink)" }}>
            Provider
          </label>
          <select
            id="create-provider"
            value={provider}
            onChange={(e) => setProvider(e.target.value as ConnectionProvider)}
            className="max-w-xs rounded-md border px-3 py-1.5 text-sm outline-none focus-visible:ring-2"
            style={{ borderColor: "var(--line)", background: "var(--surface-2)", color: "var(--ink)" }}
          >
            <option value="azure_blob">{PROVIDER_LABELS.azure_blob}</option>
            <option value="azure_postgresql">{PROVIDER_LABELS.azure_postgresql}</option>
            {dataPlaneMode === "tenant_owned" &&
              [...TENANT_OWNED_ONLY_PROVIDERS].map((p) => (
                <option key={p} value={p}>
                  {PROVIDER_LABELS[p]}
                </option>
              ))}
          </select>
        </div>

        <ProviderConfigForm
          key={provider}
          provider={provider}
          submitting={submitting}
          serverError={serverError}
          submitLabel="Create draft"
          onSubmit={onSubmit}
        />
      </div>
    </>,
    document.body,
  );
}
