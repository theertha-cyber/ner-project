import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import ContractsPage from "./page";

vi.mock("next/navigation", () => ({
  useParams: () => ({ connectionId: "conn-2" }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/settings/data-sources/conn-2/schema-contracts",
  useSearchParams: () => new URLSearchParams(""),
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

function pgConnection() {
  return {
    id: "conn-2",
    provider: "azure_postgresql",
    status: "active",
    configured_fields: ["host", "database", "username", "port", "sslmode"],
    secret_reference_fields: ["password_ref"],
    last_test: { outcome: "passed", reason_code: "none", tested_at: "2026-09-10T01:00:00Z" },
    activation: { outcome: "active", reason_code: "none", activated_at: "2026-09-10T02:00:00Z" },
    schedule: { enabled: false, cadence_minutes: null },
    replaces_connection_id: null,
    replaced_by_connection_id: null,
    created_at: "2026-09-09T00:00:00Z",
    updated_at: "2026-09-10T00:00:00Z",
  };
}

const HISTORY = {
  items: [
    { version: 3, fingerprint: "fp-3", validation_reason: "none", published: true },
    { version: 4, fingerprint: "fp-4", validation_reason: "none", published: false },
  ],
  page: 1,
  page_size: 20,
  total: 2,
  total_pages: 1,
};

describe("SchemaContractsPage", () => {
  beforeEach(() => mockAuthFetch.mockReset());

  it("renders history with publish gated on active connections", async () => {
    mockAuthFetch.mockImplementation((url: string) => {
      if (String(url).endsWith("/contracts?page=1&page_size=20")) {
        return Promise.resolve(new Response(JSON.stringify(HISTORY), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify(pgConnection()), { status: 200 }));
    });
    render(<ContractsPage />, { wrapper: Wrapper });
    expect(await screen.findByRole("heading", { name: "Schema contracts" })).toBeInTheDocument();
    expect(await screen.findByText("v3")).toBeInTheDocument();
    expect(screen.getByText("Published")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Publish validated version" })).toBeEnabled();
  });

  it("shows a first-use state when no contract exists", async () => {
    mockAuthFetch.mockImplementation((url: string) => {
      if (String(url).includes("/contracts?")) {
        return Promise.resolve(
          new Response(JSON.stringify({ items: [], page: 1, page_size: 20, total: 0, total_pages: 0 }), { status: 200 }),
        );
      }
      return Promise.resolve(new Response(JSON.stringify(pgConnection()), { status: 200 }));
    });
    render(<ContractsPage />, { wrapper: Wrapper });
    expect(await screen.findByText("No published contract yet")).toBeInTheDocument();
  });

  it("rejects invalid JSON with a recoverable form and keeps field errors safe", async () => {
    mockAuthFetch.mockImplementation((url: string) => {
      if (String(url).includes("/contracts?")) {
        return Promise.resolve(
          new Response(JSON.stringify({ items: [], page: 1, page_size: 20, total: 0, total_pages: 0 }), { status: 200 }),
        );
      }
      if (String(url).endsWith("/contracts")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({
              code: "INVALID_CONTRACT",
              message: "Not valid.",
              request_id: "req-5",
              field_errors: [{ field: "relations", message: "At least one relation is required." }],
            }),
            { status: 422 },
          ),
        );
      }
      return Promise.resolve(new Response(JSON.stringify(pgConnection()), { status: 200 }));
    });
    render(<ContractsPage />, { wrapper: Wrapper });
    await screen.findByText("No published contract yet");
    const file = new File([JSON.stringify({ version: 5 })], "contract.json", { type: "application/json" });
    await userEvent.upload(screen.getByLabelText("Choose JSON file"), file);
    const result = await screen.findByRole("alert", { name: "Contract validation result" });
    expect(result).toHaveTextContent("relations");
    expect(result).toHaveTextContent("At least one relation is required.");
    expect(result).toHaveTextContent("req-5");
    expect(screen.queryByText(/SELECT|FROM/)).not.toBeInTheDocument();
    expect(screen.getByLabelText("Choose JSON file")).toBeInTheDocument();
  });

  it("surfaces drift as a blocked state with a cross-link", async () => {
    mockAuthFetch.mockImplementation((url: string) => {
      if (String(url).includes("/publish")) {
        return Promise.resolve(
          new Response(
            JSON.stringify({ code: "PUBLISH_PRECONDITION_FAILED", message: "Drift.", request_id: "req-6" }),
            { status: 409 },
          ),
        );
      }
      if (String(url).includes("/contracts?")) {
        return Promise.resolve(new Response(JSON.stringify(HISTORY), { status: 200 }));
      }
      return Promise.resolve(new Response(JSON.stringify(pgConnection()), { status: 200 }));
    });
    render(<ContractsPage />, { wrapper: Wrapper });
    await userEvent.click(await screen.findByRole("button", { name: "Publish validated version" }));
    const blocked = await screen.findByRole("alert", { name: "Drift blocks publishing" });
    expect(blocked).toHaveTextContent("PUBLISH_PRECONDITION_FAILED");
    expect(blocked.querySelector("a")).toHaveAttribute("href", "/settings/data-sources/conn-2");
  });
});
