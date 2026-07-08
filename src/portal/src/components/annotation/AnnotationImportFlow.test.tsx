import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AnnotationPage } from "./AnnotationPage";

const mockAuthFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({ authFetch: (...args: unknown[]) => mockAuthFetch(...args) }));

const mockToast = vi.fn();
vi.mock("@/hooks/use-toast", () => ({ useToast: () => ({ toast: mockToast }) }));

const mockUseEntityTypes = vi.fn();
vi.mock("@/hooks/use-entity-types", () => ({
  useEntityTypes: () => mockUseEntityTypes(),
}));

const mockUseAuth = vi.fn();
vi.mock("@/lib/auth", () => ({
  useAuth: () => mockUseAuth(),
}));

vi.mock("@/components/ui", () => ({
  SlideOver: ({ open, children }: { open: boolean; children: React.ReactNode }) =>
    open ? <div data-testid="slide-over">{children}</div> : null,
  Spinner: () => <div data-testid="spinner" />,
}));

const mockUseAnnotationImport = vi.fn();
vi.mock("@/hooks/use-annotation-import", () => ({
  useAnnotationImport: () => mockUseAnnotationImport(),
}));

function makeQC() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}

function renderPage() {
  return render(
    <QueryClientProvider client={makeQC()}>
      <AnnotationPage />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();

  mockUseAuth.mockReturnValue({
    user: {
      userId: "ann-1",
      tenantSlug: "test-tenant",
      role: "annotator",
      email: "ann@test.com",
    },
  });

  mockUseEntityTypes.mockReturnValue({
    data: { entity_types: [{ name: "PER" }, { name: "ORG" }] },
  });

  mockUseAnnotationImport.mockReturnValue({
    state: { status: "idle" },
    importAnnotations: vi.fn(),
    reset: vi.fn(),
  });

  mockAuthFetch.mockImplementation((url: string) => {
    if (url.includes("/api/v1/annotation-tasks")) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
    }
    if (url.includes("/api/v1/tenants")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ entity_types: [{ name: "PER" }, { name: "ORG" }] }),
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
});

describe("AnnotationPage Import Button", () => {
  it("shows Import button for annotator role", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("import-btn")).toBeInTheDocument();
    });
  });

  it("shows Import button for tenant_admin role", async () => {
    mockUseAuth.mockReturnValue({
      user: {
        userId: "admin-1",
        tenantSlug: "test-tenant",
        role: "tenant_admin",
        email: "admin@test.com",
      },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("import-btn")).toBeInTheDocument();
    });
  });

  it("hides Import button for business_user role", async () => {
    mockUseAuth.mockReturnValue({
      user: {
        userId: "biz-1",
        tenantSlug: "test-tenant",
        role: "business_user",
        email: "biz@test.com",
      },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.queryByTestId("import-btn")).not.toBeInTheDocument();
    });
  });

  it("file input has correct accept attribute", async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("import-file-input")).toBeInTheDocument();
    });
    expect(screen.getByTestId("import-file-input")).toHaveAttribute("accept", ".txt,.json,.jsonl");
  });
});
