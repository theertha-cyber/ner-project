"use client";

import { useState } from "react";
import { useAuditLog } from "@/hooks/use-audit-log";
import type { AuditEvent } from "@/hooks/use-audit-log";
import { useTenants } from "@/hooks/use-tenants";
import { SearchableCombobox } from "@/components/ui/searchable-combobox";

const ALL_TENANTS_VALUE = "";

const KIND_COLORS: Record<string, { dot: string; badge: string; text: string }> = {
  create: { dot: "#3b82f6", badge: "#3b82f6", text: "#ffffff" },
  approve: { dot: "#22c55e", badge: "#22c55e", text: "#ffffff" },
  promote: { dot: "#f97316", badge: "#f97316", text: "#ffffff" },
  complete: { dot: "#22c55e", badge: "#22c55e", text: "#ffffff" },
  run: { dot: "#3b82f6", badge: "#3b82f6", text: "#ffffff" },
  reject: { dot: "#ef4444", badge: "#ef4444", text: "#ffffff" },
  update: { dot: "#eab308", badge: "#eab308", text: "#000000" },
};

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - d.getTime();
  const diffMin = Math.floor(diffMs / 60000);
  if (diffMin < 1) return "just now";
  if (diffMin < 60) return `${diffMin}m ago`;
  const diffHr = Math.floor(diffMin / 60);
  if (diffHr < 24) return `${diffHr}h ago`;
  const diffDay = Math.floor(diffHr / 24);
  if (diffDay < 7) return `${diffDay}d ago`;
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function AuditEventRow({ event }: { event: AuditEvent }) {
  const colors = KIND_COLORS[event.kind] ?? { dot: "#6b7280", badge: "#6b7280", text: "#ffffff" };

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: "14px 0",
        borderBottom: "1px solid var(--color-border)",
      }}
    >
      <div
        style={{
          width: 11,
          height: 11,
          borderRadius: "50%",
          backgroundColor: colors.dot,
          flexShrink: 0,
        }}
      />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", gap: 4 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span
            style={{
              fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
              fontSize: 13,
              fontWeight: 700,
              color: "var(--color-text-primary)",
            }}
          >
            {event.action}
          </span>
          <span
            style={{
              display: "inline-flex",
              alignItems: "center",
              borderRadius: 999,
              padding: "1px 8px",
              fontSize: 11,
              fontWeight: 600,
              lineHeight: "18px",
              backgroundColor: colors.badge,
              color: colors.text,
            }}
          >
            {event.kind}
          </span>
        </div>
        <div
          style={{
            fontSize: 12,
            color: "var(--color-text-secondary)",
            display: "flex",
            gap: 6,
            alignItems: "center",
          }}
        >
          <span>{event.target}</span>
          <span style={{ opacity: 0.4 }}>·</span>
          <span>{event.actor}</span>
          <span style={{ opacity: 0.4 }}>·</span>
          <span>{event.role.replace(/_/g, " ")}</span>
        </div>
      </div>
      <span
        style={{
          fontSize: 11,
          color: "var(--color-text-secondary)",
          whiteSpace: "nowrap",
          fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
        }}
      >
        {formatTimestamp(event.created_at)}
      </span>
    </div>
  );
}

export default function AuditPage() {
  const [page, setPage] = useState(1);
  const [selectedTenantId, setSelectedTenantId] = useState<string>(ALL_TENANTS_VALUE);
  const { data, isLoading, isError, error } = useAuditLog(page, 50, selectedTenantId || null);
  const { data: tenantsData } = useTenants();

  const tenantOptions = [
    { value: ALL_TENANTS_VALUE, label: "All Tenants" },
    ...(tenantsData?.tenants.map((t) => ({ value: t.id, label: t.name })) ?? []),
  ];

  function handleTenantChange(tenantId: string) {
    setSelectedTenantId(tenantId);
    setPage(1);
  }

  const totalPages = data ? Math.ceil(data.total / data.per_page) : 0;

  return (
    <div
      className="animate-fade-up"
      style={{
        display: "flex",
        flexDirection: "column",
        padding: "28px 32px 60px",
        maxWidth: 1040,
        width: "100%",
        margin: "0 auto",
      }}
    >
      <div
        style={{
          fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
          fontSize: 11,
          color: "var(--color-text-secondary)",
          letterSpacing: "0.06em",
          marginBottom: 8,
        }}
      >
        SYSTEM ADMIN ◦ AUDIT
      </div>

      <h1
        style={{
          fontFamily: "var(--font-display, 'Hanken Grotesk', sans-serif)",
          fontSize: 28,
          fontWeight: 600,
          color: "var(--color-text-primary)",
          margin: 0,
        }}
      >
        Audit Log
      </h1>

      <div
        style={{
          fontSize: 12,
          color: "var(--color-text-secondary)",
          fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
          marginTop: 4,
          marginBottom: 16,
        }}
      >
        tenant.audit_log · {data ? `${data.total} events` : "\u00A0"}
      </div>

      <div style={{ marginBottom: 24, maxWidth: 320 }}>
        <SearchableCombobox
          value={selectedTenantId}
          onChange={handleTenantChange}
          options={tenantOptions}
          ariaLabel="Filter by tenant"
          placeholder="Search tenants..."
        />
      </div>

      {isLoading && (
        <div style={{ padding: 24, textAlign: "center", color: "var(--color-text-secondary)" }}>
          Loading...
        </div>
      )}

      {isError && (
        <div style={{ padding: 24, textAlign: "center", color: "var(--color-error)" }}>
          {error?.message ?? "Failed to load audit log"}
        </div>
      )}

      {data && data.events.length === 0 && (
        <div
          style={{
            padding: 32,
            textAlign: "center",
            color: "var(--color-text-secondary)",
            fontSize: 13,
          }}
        >
          {selectedTenantId ? "No audit events for this tenant" : "No events recorded yet"}
        </div>
      )}

      {data && data.events.length > 0 && (
        <div>
          {data.events.map((event) => (
            <AuditEventRow key={event.id} event={event} />
          ))}
        </div>
      )}

      {data && totalPages > 1 && (
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            gap: 12,
            marginTop: 28,
          }}
        >
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1}
            style={{
              padding: "8px 18px",
              borderRadius: 8,
              border: "1px solid var(--color-border)",
              background: "var(--color-surface-raised)",
              color: "var(--color-text-primary)",
              fontSize: 12,
              fontWeight: 600,
              cursor: page <= 1 ? "default" : "pointer",
              opacity: page <= 1 ? 0.4 : 1,
            }}
          >
            ← Previous
          </button>
          <span
            style={{
              fontSize: 12,
              color: "var(--color-text-secondary)",
              fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
            }}
          >
            Page {page} of {totalPages}
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages}
            style={{
              padding: "8px 18px",
              borderRadius: 8,
              border: "1px solid var(--color-border)",
              background: "var(--color-surface-raised)",
              color: "var(--color-text-primary)",
              fontSize: 12,
              fontWeight: 600,
              cursor: page >= totalPages ? "default" : "pointer",
              opacity: page >= totalPages ? 0.4 : 1,
            }}
          >
            Next →
          </button>
        </div>
      )}
    </div>
  );
}
