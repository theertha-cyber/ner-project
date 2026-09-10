"use client";

import { useState } from "react";
import { Badge, type BadgeVariant } from "@/components/ui/badge";
import { STATUS_LABELS, type ConnectionStatus } from "@/lib/data-sources";

const STATUS_VARIANTS: Record<ConnectionStatus, BadgeVariant> = {
  draft: "inactive",
  validated: "promoted",
  active: "active",
  paused: "pending_approval",
  error: "failed",
  retired: "archived",
};

/** CMP-3 — safe status badge. Colour is never the sole signal: the text label always renders. */
export function SafeStatusBadge({ status }: { status: ConnectionStatus }) {
  return (
    <span role="status" aria-label={`Status: ${STATUS_LABELS[status]}`}>
      <Badge variant={STATUS_VARIANTS[status]} label={STATUS_LABELS[status]} />
    </span>
  );
}

export type OutcomeVariant = "success" | "warning" | "blocked" | "error";

const VARIANT_STYLES: Record<OutcomeVariant, { border: string; soft: string; title: string }> = {
  success: { border: "var(--good)", soft: "var(--good-soft)", title: "var(--good)" },
  warning: { border: "var(--color-warning)", soft: "var(--color-surface-raised)", title: "var(--color-warning)" },
  blocked: { border: "var(--color-warning)", soft: "var(--color-surface-raised)", title: "var(--color-warning)" },
  error: { border: "var(--bad)", soft: "var(--bad-soft)", title: "var(--bad)" },
};

export interface SafeOutcomeNoticeProps {
  variant: OutcomeVariant;
  title: string;
  code?: string;
  requestId?: string;
  replayed?: boolean;
  /** Dismissal is refused for blocking notices so an activation or drift block cannot be hidden. */
  dismissible?: boolean;
  children?: React.ReactNode;
}

/** CMP-8 — finite safe outcome notice. Renders code + request ID only, never provider payloads. */
export function SafeOutcomeNotice({
  variant,
  title,
  code,
  requestId,
  replayed,
  dismissible = true,
  children,
}: SafeOutcomeNoticeProps) {
  const [dismissed, setDismissed] = useState(false);
  const styles = VARIANT_STYLES[variant];
  const canDismiss = dismissible && variant !== "blocked";
  if (dismissed) return null;
  const urgent = variant === "error" || variant === "blocked";
  return (
    <div
      role={urgent ? "alert" : "status"}
      aria-label={title}
      className="rounded-md border p-4"
      style={{ borderColor: styles.border, background: styles.soft }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold" style={{ color: styles.title }}>
            {title}
          </p>
          {code && (
            <p className="mt-1 font-mono text-xs" style={{ color: "var(--ink-2)" }}>
              {code}
              {requestId ? ` · Request ${requestId}` : ""}
              {replayed ? " · Replayed safely — no duplicate effect" : ""}
            </p>
          )}
          {children && (
            <div className="mt-2 text-sm" style={{ color: "var(--ink-2)" }}>
              {children}
            </div>
          )}
        </div>
        {canDismiss && (
          <button
            type="button"
            onClick={() => setDismissed(true)}
            aria-label="Dismiss notice"
            className="rounded-sm px-2 py-1 text-sm outline-none focus-visible:ring-2"
            style={{ color: "var(--ink-2)" }}
          >
            Dismiss
          </button>
        )}
      </div>
    </div>
  );
}
