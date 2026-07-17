"use client";
// ^ This page uses React state (useState) and click handlers, so it must run in
//   the browser. Any page that uses hooks or interactivity needs this line at the top.

import { useState } from "react";

// ---------------------------------------------------------------------------
// 1. DATA
// In a real page this would come from a hook (e.g. useReportsData) that fetches
// from your backend — see hooks/use-dashboard-data.ts for that pattern.
// Here we hard-code some demo data so the page renders instantly with no backend.
// ---------------------------------------------------------------------------
interface Report {
  id: string;
  name: string;
  entities: number;
  status: "ready" | "running";
}

const DEMO_REPORTS: Report[] = [
  { id: "r1", name: "Contracts — Q3", entities: 1284, status: "ready" },
  { id: "r2", name: "Invoices — July", entities: 642, status: "running" },
  { id: "r3", name: "Support tickets", entities: 3910, status: "ready" },
  { id: "r4", name: "Onboarding forms", entities: 218, status: "ready" },
];

// ---------------------------------------------------------------------------
// 2. THE PAGE
// A page is just a function that returns JSX. It MUST be the default export.
// ---------------------------------------------------------------------------
export default function ReportsPage() {
  // `useState` gives us a piece of memory that survives re-renders.
  // `query` holds the current search text; `setQuery` updates it.
  // When setQuery runs, React re-renders this component with the new value.
  const [query, setQuery] = useState("");

  // Derive the filtered list from state. We don't store this in state — we just
  // recompute it every render. `.filter()` keeps only the rows that match.
  const visible = DEMO_REPORTS.filter((r) =>
    r.name.toLowerCase().includes(query.toLowerCase())
  );

  return (
    <div
      className="animate-fade-up"
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 24,
        padding: "28px 32px 60px",
        maxWidth: 1240,
        margin: "0 auto",
        width: "100%",
      }}
    >
      {/* Breadcrumb — same style as the dashboard page */}
      <div
        style={{
          fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)",
          fontSize: 11,
          color: "var(--color-text-secondary)",
          letterSpacing: "0.06em",
        }}
      >
        REPORTS ◦ DEMO
      </div>

      <h1 style={{ fontSize: 28, fontWeight: 600, color: "var(--color-text-primary)" }}>
        Reports
      </h1>

      {/* A controlled input: its value comes FROM state, and typing writes BACK
          to state via onChange. This two-way binding is the core React pattern. */}
      <input
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Filter reports…"
        style={{
          padding: "10px 14px",
          borderRadius: 8,
          border: "1px solid var(--color-border)",
          background: "var(--color-surface-raised)",
          color: "var(--color-text-primary)",
          fontSize: 14,
          maxWidth: 320,
        }}
      />

      {/* A list. We turn the `visible` array into an array of rows with .map().
          React requires a unique `key` on each item so it can track them. */}
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {visible.length === 0 ? (
          // Conditional rendering: show a message when nothing matches.
          <p style={{ color: "var(--color-text-secondary)", fontSize: 14 }}>
            No reports match “{query}”.
          </p>
        ) : (
          visible.map((report) => <ReportRow key={report.id} report={report} />)
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 3. A CHILD COMPONENT
// Broken out to show how pages compose smaller pieces. It receives data via
// `props` (here, a single `report` prop) and just renders it. Data flows DOWN.
// ---------------------------------------------------------------------------
function ReportRow({ report }: { report: Report }) {
  const isReady = report.status === "ready";

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "14px 18px",
        borderRadius: 12,
        border: "1px solid var(--color-border)",
        background: "var(--color-surface-raised)",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        <span style={{ fontSize: 15, fontWeight: 500, color: "var(--color-text-primary)" }}>
          {report.name}
        </span>
        <span style={{ fontSize: 12, color: "var(--color-text-secondary)" }}>
          {report.entities.toLocaleString()} entities
        </span>
      </div>

      {/* A little status pill. Its color/text depend on the report's status. */}
      <span
        style={{
          fontSize: 11,
          fontWeight: 600,
          padding: "4px 10px",
          borderRadius: 999,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          color: isReady ? "#0a7d34" : "#8a5a00",
          background: isReady ? "rgba(16,185,129,0.12)" : "rgba(245,158,11,0.14)",
        }}
      >
        {report.status}
      </span>
    </div>
  );
}
