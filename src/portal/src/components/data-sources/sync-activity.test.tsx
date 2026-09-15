import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SyncActivitySummary } from "./lifecycle";
import { useDataSource } from "@/hooks/use-data-sources";
import type { SafeConnection } from "@/lib/data-sources";

const mockAuthFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({
  authFetch: (...args: unknown[]) => mockAuthFetch(...args),
}));

function renderWithClient(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

function connection(overrides: Partial<SafeConnection> = {}): SafeConnection {
  return {
    id: "conn-1",
    provider: "azure_blob",
    status: "active",
    configured_fields: ["account", "container"],
    secret_reference_fields: ["connection_string_ref"],
    last_test: { outcome: "passed", reason_code: "none", tested_at: "2026-09-10T01:00:00Z" },
    activation: { outcome: "active", reason_code: "none", activated_at: "2026-09-10T02:00:00Z" },
    schedule: { enabled: true, cadence_minutes: 15 },
    last_sync: { outcome: "never_run", completed_at: null },
    replaces_connection_id: null,
    replaced_by_connection_id: null,
    created_at: "2026-09-09T00:00:00Z",
    updated_at: "2026-09-10T00:00:00Z",
    ...overrides,
  };
}

const ENQUEUED = { connection_id: "conn-1", trigger: "manual", outcome: "enqueued", enqueued_at: "2026-09-11T08:00:00Z" };

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function syncCalls() {
  return mockAuthFetch.mock.calls.filter(([, init]) => (init as RequestInit | undefined)?.method === "POST") as [
    string,
    RequestInit,
  ][];
}

/** Detail-view stand-in: the panel is fed by the same detail query the page uses. */
function Harness() {
  const { data } = useDataSource("conn-1");
  return data ? <SyncActivitySummary connection={data} /> : null;
}

describe("SyncActivitySummary sync-now control", () => {
  beforeEach(() => mockAuthFetch.mockReset());

  it("queues a manual sync with a fresh key, shows pending then success, and refreshes last run", async () => {
    let resolveSync!: (r: Response) => void;
    let detailReads = 0;
    mockAuthFetch.mockImplementation((_url: string, init?: RequestInit) => {
      if (init?.method === "POST") return new Promise<Response>((resolve) => (resolveSync = resolve));
      detailReads += 1;
      return Promise.resolve(
        json(detailReads === 1 ? connection() : connection({ last_sync: { outcome: "succeeded", completed_at: "2026-09-11T08:01:00Z" } })),
      );
    });

    renderWithClient(<Harness />);
    expect(await screen.findByText("never run")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sync now" }));

    expect(await screen.findByRole("status", { name: "Sync pending" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Starting sync…" })).toBeDisabled();
    const [url, init] = syncCalls()[0];
    expect(url).toBe("/api/v1/data-sources/conn-1/sync");
    expect(new Headers(init.headers).get("Idempotency-Key")).toMatch(/^[\x20-\x7E]{1,128}$/);

    resolveSync(json(ENQUEUED, 202));
    expect(await screen.findByRole("status", { name: "Sync queued" })).toBeInTheDocument();
    expect(await screen.findByText(/^succeeded · /)).toBeInTheDocument();
    expect(detailReads).toBe(2);
  });

  it("sends a fresh Idempotency-Key on every click", async () => {
    mockAuthFetch.mockImplementation((_url: string, init?: RequestInit) =>
      Promise.resolve(init?.method === "POST" ? json(ENQUEUED, 202) : json(connection())),
    );
    renderWithClient(<Harness />);
    await userEvent.click(await screen.findByRole("button", { name: "Sync now" }));
    await screen.findByRole("status", { name: "Sync queued" });
    await userEvent.click(await screen.findByRole("button", { name: "Sync now" }));
    await waitFor(() => expect(syncCalls()).toHaveLength(2));
    const [first, second] = syncCalls().map(([, init]) => new Headers(init.headers).get("Idempotency-Key"));
    expect(first).toBeTruthy();
    expect(second).toBeTruthy();
    expect(first).not.toBe(second);
  });

  it("disables sync-now with a blocked notice and sends nothing for inactive connections", async () => {
    renderWithClient(<SyncActivitySummary connection={connection({ status: "paused", schedule: { enabled: false, cadence_minutes: null } })} />);
    const button = screen.getByRole("button", { name: "Sync now" });
    expect(button).toBeDisabled();
    expect(screen.getByRole("alert", { name: "Sync unavailable" })).toHaveTextContent("INACTIVE_CONNECTION");
    await userEvent.click(button);
    expect(mockAuthFetch).not.toHaveBeenCalled();
  });

  it("presents no sync-now control for PostgreSQL and keeps the exemption notice", () => {
    const pg = connection({ id: "conn-2", provider: "azure_postgresql", schedule: { enabled: false, cadence_minutes: null } });
    delete (pg as Partial<SafeConnection>).last_sync;
    renderWithClient(<SyncActivitySummary connection={pg} />);
    expect(screen.queryByRole("button", { name: "Sync now" })).not.toBeInTheDocument();
    expect(screen.getByText(/Sync scheduling does not apply to PostgreSQL/)).toBeInTheDocument();
    expect(mockAuthFetch).not.toHaveBeenCalled();
  });

  it("shows a safe 'sync already running' notice when the refreshed run is lease-held", async () => {
    let detailReads = 0;
    mockAuthFetch.mockImplementation((_url: string, init?: RequestInit) => {
      if (init?.method === "POST") return Promise.resolve(json(ENQUEUED, 202));
      detailReads += 1;
      return Promise.resolve(
        json(detailReads === 1 ? connection() : connection({ last_sync: { outcome: "lease_held", completed_at: "2026-09-11T08:00:30Z" } })),
      );
    });
    const { container } = renderWithClient(<Harness />);
    await userEvent.click(await screen.findByRole("button", { name: "Sync now" }));

    expect(await screen.findByRole("status", { name: "Sync already running" })).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: "Sync queued" })).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(container.textContent).not.toMatch(/lease_held|Traceback|amqp|connection_string/i);
  });

  it("renders a finite safe error when the trigger is refused", async () => {
    mockAuthFetch.mockImplementation((_url: string, init?: RequestInit) =>
      Promise.resolve(
        init?.method === "POST"
          ? json({ error: { code: "SYNC_UNAVAILABLE", message: "The sync queue is temporarily unavailable.", request_id: "req-7" } }, 503)
          : json(connection()),
      ),
    );
    renderWithClient(<Harness />);
    await userEvent.click(await screen.findByRole("button", { name: "Sync now" }));
    const notice = await screen.findByRole("alert", { name: "Sync not started" });
    expect(notice).toHaveTextContent("SYNC_UNAVAILABLE · Request req-7");
    expect(screen.queryByRole("status", { name: "Sync queued" })).not.toBeInTheDocument();
  });
});
