"use client";

import { ReactNode } from "react";
import { useDataPlaneStatus } from "@/hooks/use-data-plane";
import { SafeApiHttpError } from "@/hooks/use-data-sources";
import { DATA_PLANE_BLOCKING_STATUSES, type DataPlaneStatus } from "@/lib/data-sources";
import { Spinner } from "@/components/ui/spinner";

/* ADR-017, task 13.3 — wraps documents, extraction, annotation, training,
 * analytics, and chat pages: a `tenant_owned` tenant whose data plane is not
 * `ready` sees a safe status state here instead of the page's own content, and
 * a request that lands mid-outage (`TENANT_DATA_PLANE_UNAVAILABLE`) never
 * renders cached content underneath it — this component owns the decision of
 * whether the wrapped page is allowed to render at all. */

const STATUS_COPY: Record<DataPlaneStatus, { title: string; body: string }> = {
  awaiting_store: {
    title: "Data plane not configured yet",
    body: "This tenant is set up to host its own data, but no store has been connected yet. A tenant admin can add one from Data Sources.",
  },
  provisioning: {
    title: "Setting up your data plane",
    body: "Your tenant-owned store is being provisioned. This usually takes a few minutes — this page will become available automatically once it's ready.",
  },
  provisioning_failed: {
    title: "Data plane setup failed",
    body: "Provisioning your tenant-owned store did not complete. A tenant admin can retry from Data Sources.",
  },
  migration_required: {
    title: "Data plane needs a maintenance update",
    body: "Your tenant-owned store is pending a routine update before it can serve content again. This resolves automatically — no action needed.",
  },
  paused: {
    title: "Data plane connection paused",
    body: "The connection to your tenant-owned store is currently paused. A tenant admin can reactivate it from Data Sources.",
  },
  store_retired: {
    title: "Data plane retired",
    body: "This tenant's data-plane connection has been retired and is no longer active.",
  },
  ready: { title: "", body: "" },
};

function BlockedState({ status, reasonClass }: { status: DataPlaneStatus; reasonClass?: string }) {
  const copy = STATUS_COPY[status];
  return (
    <div
      role="status"
      className="flex min-h-[50vh] flex-col items-center justify-center gap-2 rounded-md border p-8 text-center"
      style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}
    >
      <h2 className="text-lg font-semibold" style={{ color: "var(--ink)" }}>
        {copy.title}
      </h2>
      <p className="max-w-md text-sm" style={{ color: "var(--ink-2)" }}>
        {copy.body}
      </p>
      {reasonClass && (
        <p className="text-xs" style={{ color: "var(--ink-3, var(--ink-2))" }}>
          Reason: {reasonClass}
        </p>
      )}
    </div>
  );
}

function UnavailableState({ reasonClass }: { reasonClass?: string }) {
  return (
    <div
      role="status"
      className="flex min-h-[50vh] flex-col items-center justify-center gap-2 rounded-md border p-8 text-center"
      style={{ borderColor: "var(--line)", background: "var(--surface-2)" }}
    >
      <h2 className="text-lg font-semibold" style={{ color: "var(--ink)" }}>
        Your data plane is temporarily unavailable
      </h2>
      <p className="max-w-md text-sm" style={{ color: "var(--ink-2)" }}>
        We couldn&apos;t reach your tenant-owned store just now. This is usually temporary — try again shortly.
      </p>
      {reasonClass && (
        <p className="text-xs" style={{ color: "var(--ink-3, var(--ink-2))" }}>
          Reason: {reasonClass}
        </p>
      )}
    </div>
  );
}

export interface DataPlaneGateProps {
  children: ReactNode;
}

export function DataPlaneGate({ children }: DataPlaneGateProps) {
  const { data, isLoading, isError, error } = useDataPlaneStatus();

  if (isLoading) {
    return (
      <div className="flex min-h-[50vh] items-center justify-center">
        <Spinner size="md" />
      </div>
    );
  }

  if (isError) {
    if (error instanceof SafeApiHttpError) {
      if (error.code === "TENANT_DATA_PLANE_UNAVAILABLE") {
        return <UnavailableState reasonClass={error.reasonClass} />;
      }
      if (error.code === "TENANT_DATA_PLANE_NOT_READY" && error.statusClass) {
        return <BlockedState status={error.statusClass as DataPlaneStatus} />;
      }
    }
    // An error unrelated to data-plane readiness (network hiccup fetching
    // status, auth expiry, etc.) is not this component's decision to render —
    // let the wrapped page's own error handling and the request itself decide.
    return <>{children}</>;
  }

  if (data && DATA_PLANE_BLOCKING_STATUSES.has(data.status)) {
    return <BlockedState status={data.status} reasonClass={data.status_reason} />;
  }

  return <>{children}</>;
}
