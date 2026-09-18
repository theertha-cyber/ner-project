import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DataPlaneGate } from "./data-plane-gate";

const mockAuthFetch = vi.fn();

vi.mock("@/lib/auth-fetch", () => ({
  authFetch: (...args: unknown[]) => mockAuthFetch(...args),
}));

function renderGated() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <DataPlaneGate>
        <div>protected content</div>
      </DataPlaneGate>
    </QueryClientProvider>,
  );
}

describe("DataPlaneGate", () => {
  beforeEach(() => mockAuthFetch.mockReset());

  it("scenario #74: an awaiting-store tenant is guided to setup, not shown content", async () => {
    mockAuthFetch.mockResolvedValue(
      new Response(
        JSON.stringify({ mode: "tenant_owned", status: "awaiting_store", status_reason: "none", store_id: null, schema_revision: null }),
        { status: 200 },
      ),
    );

    renderGated();

    await waitFor(() => expect(screen.getByText(/data plane not configured yet/i)).toBeInTheDocument());
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
  });

  it("scenario #75: an outage is shown without rendering the wrapped page's content", async () => {
    mockAuthFetch.mockResolvedValue(
      new Response(
        JSON.stringify({ error: { code: "TENANT_DATA_PLANE_UNAVAILABLE", reason_class: "unreachable", request_id: "req-1" } }),
        { status: 503 },
      ),
    );

    renderGated();

    await waitFor(() => expect(screen.getByText(/temporarily unavailable/i)).toBeInTheDocument());
    expect(screen.getByText(/unreachable/i)).toBeInTheDocument();
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
  });

  it("does not retry a server rejection before rendering the page", async () => {
    mockAuthFetch.mockResolvedValue(
      new Response(JSON.stringify({ error: { code: "FORBIDDEN", request_id: "req-2" } }), { status: 403 }),
    );

    // Client default retries are left on, so only the hook's own policy can keep this fast.
    render(
      <QueryClientProvider client={new QueryClient()}>
        <DataPlaneGate>
          <div>protected content</div>
        </DataPlaneGate>
      </QueryClientProvider>,
    );

    await waitFor(() => expect(screen.getByText("protected content")).toBeInTheDocument(), { timeout: 500 });
    expect(mockAuthFetch).toHaveBeenCalledTimes(1);
  });

  it("renders the wrapped content for a ready data plane", async () => {
    mockAuthFetch.mockResolvedValue(
      new Response(
        JSON.stringify({ mode: "platform", status: "ready", status_reason: "none", store_id: null, schema_revision: null }),
        { status: 200 },
      ),
    );

    renderGated();

    await waitFor(() => expect(screen.getByText("protected content")).toBeInTheDocument());
  });

  it("renders the wrapped content for a paused data plane's error only as blocked state, not silently", async () => {
    mockAuthFetch.mockResolvedValue(
      new Response(
        JSON.stringify({ mode: "tenant_owned", status: "paused", status_reason: "connection_paused", store_id: "s1", schema_revision: 1 }),
        { status: 200 },
      ),
    );

    renderGated();

    await waitFor(() => expect(screen.getByText(/data plane connection paused/i)).toBeInTheDocument());
    expect(screen.getByText(/connection_paused/i)).toBeInTheDocument();
    expect(screen.queryByText("protected content")).not.toBeInTheDocument();
  });
});
