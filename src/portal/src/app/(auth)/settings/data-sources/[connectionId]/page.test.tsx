import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import DetailPage from "./page";

vi.mock("next/navigation", () => ({
  useParams: () => ({ connectionId: "conn-1" }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn(), back: vi.fn() }),
  usePathname: () => "/settings/data-sources/conn-1",
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

function blobConnection(overrides = {}) {
  return {
    id: "conn-1",
    provider: "azure_blob",
    status: "draft",
    configured_fields: ["account", "container"],
    secret_reference_fields: ["connection_string_ref"],
    last_test: { outcome: "not_run", reason_code: "none", tested_at: null },
    activation: { outcome: "inactive", reason_code: "none", activated_at: null },
    schedule: { enabled: false, cadence_minutes: null },
    last_sync: { outcome: "never_run", completed_at: null },
    replaces_connection_id: null,
    replaced_by_connection_id: null,
    created_at: "2026-09-09T00:00:00Z",
    updated_at: "2026-09-10T00:00:00Z",
    ...overrides,
  };
}

describe("DataSourceDetailPage", () => {
  beforeEach(() => mockAuthFetch.mockReset());

  it("renders safe facts with field names and no values", async () => {
    mockAuthFetch.mockResolvedValue(new Response(JSON.stringify(blobConnection()), { status: 200 }));
    render(<DetailPage />, { wrapper: Wrapper });
    expect(await screen.findByRole("heading", { name: "Azure Blob Storage" })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Status: Draft" })).toBeInTheDocument();
    const facts = screen.getByRole("region", { name: "Connection facts" });
    expect(within(facts).getByText("account, container")).toBeInTheDocument();
    expect(within(facts).getByText("connection_string_ref")).toBeInTheDocument();
    expect(screen.queryByText(/secret-value/)).not.toBeInTheDocument();
  });

  it("blocks activation safely until test and evidence pass", async () => {
    mockAuthFetch.mockResolvedValue(new Response(JSON.stringify(blobConnection()), { status: 200 }));
    render(<DetailPage />, { wrapper: Wrapper });
    await screen.findByRole("heading", { name: "Azure Blob Storage" });
    expect(screen.getByRole("alert", { name: "Activation unavailable" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Activate" })).toBeDisabled();
  });

  it("activates with evidence after a passed test", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      new Response(JSON.stringify(blobConnection({ last_test: { outcome: "passed", reason_code: "none", tested_at: "2026-09-10T01:00:00Z" } })), { status: 200 }),
    );
    mockAuthFetch.mockResolvedValue(
      new Response(JSON.stringify(blobConnection({ status: "active" })), { status: 200 }),
    );
    render(<DetailPage />, { wrapper: Wrapper });
    await screen.findByRole("heading", { name: "Azure Blob Storage" });
    await userEvent.click(screen.getByRole("checkbox", { name: "network_approved" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "governance_approved" }));
    const activate = screen.getByRole("button", { name: "Activate" });
    expect(activate).toBeEnabled();
    await userEvent.click(activate);
    await waitFor(() => expect(mockAuthFetch).toHaveBeenCalledTimes(2));
    const [url, init] = mockAuthFetch.mock.calls[1] as [string, RequestInit];
    expect(url).toBe("/api/v1/data-sources/conn-1/activate");
    expect(JSON.parse(String(init.body))).toEqual({ activation_evidence: ["governance_approved", "network_approved"] });
    expect(new Headers(init.headers).get("Idempotency-Key")).toBeTruthy();
  });

  it("requires confirmation before retiring", async () => {
    mockAuthFetch.mockResolvedValueOnce(new Response(JSON.stringify(blobConnection()), { status: 200 }));
    mockAuthFetch.mockResolvedValue(
      new Response(JSON.stringify(blobConnection({ status: "retired" })), { status: 200 }),
    );
    render(<DetailPage />, { wrapper: Wrapper });
    await screen.findByRole("heading", { name: "Azure Blob Storage" });
    await userEvent.click(screen.getByRole("button", { name: "Retire source" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText(/Retirement is terminal/)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(mockAuthFetch).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole("button", { name: "Retire source" }));
    await userEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Confirm" }));
    await waitFor(() => expect(mockAuthFetch).toHaveBeenCalledTimes(2));
    const [url, init] = mockAuthFetch.mock.calls[1] as [string, RequestInit];
    expect(url).toBe("/api/v1/data-sources/conn-1/retire");
    expect(JSON.parse(String(init.body))).toEqual({ confirm: true });
  });

  it("announces idempotent replay without duplicating effect", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      new Response(JSON.stringify(blobConnection({ last_test: { outcome: "passed", reason_code: "none", tested_at: "2026-09-10T01:00:00Z" } })), { status: 200 }),
    );
    mockAuthFetch.mockResolvedValue(
      new Response(JSON.stringify(blobConnection()), { status: 200, headers: { "Idempotent-Replay": "true" } }),
    );
    render(<DetailPage />, { wrapper: Wrapper });
    await screen.findByRole("heading", { name: "Azure Blob Storage" });
    await userEvent.click(screen.getByRole("button", { name: "Test connection" }));
    await waitFor(() => expect(mockAuthFetch).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole("status", { name: "Already applied" })).toHaveTextContent(/no duplicate effect/);
  });

  it("omits schedule for PostgreSQL and links to schema contracts", async () => {
    const pg = blobConnection({
      id: "conn-2",
      provider: "azure_postgresql",
      status: "active",
      schedule: { enabled: false, cadence_minutes: null },
    });
    delete (pg as Record<string, unknown>).last_sync;
    mockAuthFetch.mockResolvedValue(new Response(JSON.stringify(pg), { status: 200 }));
    render(<DetailPage />, { wrapper: Wrapper });
    await screen.findByRole("heading", { name: "Azure Database for PostgreSQL" });
    expect(screen.getByText(/Sync scheduling does not apply to PostgreSQL/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Manage schema contracts" })).toHaveAttribute(
      "href",
      "/settings/data-sources/conn-2/schema-contracts",
    );
  });
});
