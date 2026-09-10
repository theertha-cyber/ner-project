import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DataSourcesPage from "./page";

const navState = vi.hoisted(() => ({
  params: "",
  replace: vi.fn(),
  push: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(navState.params),
  useRouter: () => ({ replace: navState.replace, push: navState.push }),
  usePathname: () => "/settings/data-sources",
}));

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={typeof href === "string" ? href : "#"} {...rest}>
      {children}
    </a>
  ),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { userId: "u-1", tenantId: "t-1", role: "tenant_admin", email: "a@t.test", tenantSlug: "t" },
    getAccessToken: () => "tok",
    setAccessToken: () => {},
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));

const mockAuthFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({
  authFetch: (...args: unknown[]) => mockAuthFetch(...args),
}));

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const CONNECTION = {
  id: "conn-1",
  provider: "azure_blob",
  status: "active",
  configured_fields: ["account", "container"],
  secret_reference_fields: ["connection_string_ref"],
  last_test: { outcome: "passed", reason_code: "none", tested_at: "2026-09-10T01:00:00Z" },
  activation: { outcome: "active", reason_code: "none", activated_at: "2026-09-10T02:00:00Z" },
  schedule: { enabled: true, cadence_minutes: 60 },
  last_sync: { outcome: "succeeded", completed_at: "2026-09-10T03:00:00Z" },
  replaces_connection_id: null,
  replaced_by_connection_id: null,
  created_at: "2026-09-09T00:00:00Z",
  updated_at: "2026-09-10T03:00:00Z",
};

const PAGE = { items: [CONNECTION], total: 21, page: 1, page_size: 20, total_pages: 2 };

describe("DataSourcesPage", () => {
  beforeEach(() => {
    mockAuthFetch.mockReset();
    navState.replace.mockClear();
    navState.push.mockClear();
    navState.params = "";
  });

  it("renders the collection with safe statuses and pagination range", async () => {
    mockAuthFetch.mockResolvedValue(new Response(JSON.stringify(PAGE), { status: 200 }));
    render(<DataSourcesPage />, { wrapper: Wrapper });
    expect(await screen.findByRole("heading", { name: "Data Sources" })).toBeInTheDocument();
    expect(await screen.findByText("Azure Blob Storage")).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Status: Active" })).toHaveTextContent("Active");
    expect(screen.getByText("Showing 1–20 of 21")).toBeInTheDocument();
    const manage = screen.getByRole("link", { name: "Manage Azure Blob Storage connection" });
    expect(manage).toHaveAttribute("href", "/settings/data-sources/conn-1");
  });

  it("resets to page 1 in the URL when a filter changes", async () => {
    mockAuthFetch.mockResolvedValue(new Response(JSON.stringify(PAGE), { status: 200 }));
    navState.params = "page=2";
    render(<DataSourcesPage />, { wrapper: Wrapper });
    await screen.findByText("Azure Blob Storage");
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Filter by provider" }), "azure_blob");
    await waitFor(() => expect(navState.replace).toHaveBeenCalled());
    const target = String(navState.replace.mock.calls.at(-1)?.[0] ?? "");
    expect(target).toContain("provider=azure_blob");
    expect(target).not.toContain("page=");
  });

  it("shows a filtered-empty state that echoes the query", async () => {
    mockAuthFetch.mockResolvedValue(
      new Response(JSON.stringify({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 }), { status: 200 }),
    );
    navState.params = "q=zzz";
    render(<DataSourcesPage />, { wrapper: Wrapper });
    expect(await screen.findByRole("heading", { name: /No matches/ })).toHaveTextContent("zzz");
    await userEvent.click(screen.getByRole("button", { name: "Clear search and filters" }));
    expect(navState.replace).toHaveBeenCalledWith("/settings/data-sources");
  });

  it("shows a first-use empty state with a creation call to action", async () => {
    mockAuthFetch.mockResolvedValue(
      new Response(JSON.stringify({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 }), { status: 200 }),
    );
    render(<DataSourcesPage />, { wrapper: Wrapper });
    expect(await screen.findByRole("heading", { name: "No data sources yet" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Configure the first connection" }));
    expect(screen.getByRole("region", { name: "Create connection" })).toBeInTheDocument();
  });

  it("renders safe errors with retry and never leaks provider diagnostics", async () => {
    mockAuthFetch.mockResolvedValue(
      new Response(
        JSON.stringify({
          code: "INVALID_REQUEST",
          message: "Unknown sort field.",
          request_id: "req-7",
          provider_detail: "tls handshake failed at 10.0.0.9",
        }),
        { status: 422 },
      ),
    );
    render(<DataSourcesPage />, { wrapper: Wrapper });
    const alert = await screen.findByRole("alert", { name: "Connections unavailable" });
    expect(alert).toHaveTextContent("INVALID_REQUEST");
    expect(alert).toHaveTextContent("req-7");
    expect(screen.queryByText(/tls handshake/)).not.toBeInTheDocument();
    mockAuthFetch.mockResolvedValue(new Response(JSON.stringify(PAGE), { status: 200 }));
    await userEvent.click(within(alert).getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(mockAuthFetch.mock.calls.length).toBeGreaterThan(1));
  });
});
