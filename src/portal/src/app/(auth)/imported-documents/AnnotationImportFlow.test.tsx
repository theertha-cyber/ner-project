import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import ImportedDocumentsPage from "./page";

const mockAuthFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({ authFetch: (...args: unknown[]) => mockAuthFetch(...args) }));

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

function renderPage() {
  return render(<ImportedDocumentsPage />);
}

beforeEach(() => {
  vi.clearAllMocks();

  mockUseEntityTypes.mockReturnValue({
    data: { entity_types: [{ name: "PER" }, { name: "ORG" }] },
  });

  mockUseAnnotationImport.mockReturnValue({
    state: { status: "idle" },
    importAnnotations: vi.fn(),
    reset: vi.fn(),
  });

  mockAuthFetch.mockImplementation(() =>
    Promise.resolve({ ok: true, json: () => Promise.resolve({ items: [], total: 0, page: 1, per_page: 20 }) }),
  );
});

describe("Imported Documents page — Import button", () => {
  it("shows Import button for annotator role", async () => {
    mockUseAuth.mockReturnValue({
      user: { userId: "ann-1", tenantSlug: "test-tenant", role: "annotator", email: "ann@test.com" },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Import file")).toBeInTheDocument();
    });
  });

  it("shows Import button for tenant_admin role", async () => {
    mockUseAuth.mockReturnValue({
      user: { userId: "admin-1", tenantSlug: "test-tenant", role: "tenant_admin", email: "admin@test.com" },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByText("Import file")).toBeInTheDocument();
    });
  });

  it("hides Import button for business_user role", async () => {
    mockUseAuth.mockReturnValue({
      user: { userId: "biz-1", tenantSlug: "test-tenant", role: "business_user", email: "biz@test.com" },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.queryByText("Import file")).not.toBeInTheDocument();
    });
  });

  it("file input has correct accept attribute", async () => {
    mockUseAuth.mockReturnValue({
      user: { userId: "ann-1", tenantSlug: "test-tenant", role: "annotator", email: "ann@test.com" },
    });
    renderPage();
    await waitFor(() => {
      expect(screen.getByTestId("import-file-input")).toBeInTheDocument();
    });
    expect(screen.getByTestId("import-file-input")).toHaveAttribute("accept", ".txt,.json,.jsonl");
  });
});
