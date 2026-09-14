import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: mockPush })),
}));

let mockUser: { role: string; userId: string; tenantSlug: string } = {
  role: "tenant_admin",
  userId: "admin-1",
  tenantSlug: "acme",
};

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(() => ({ user: mockUser })),
}));

import ManualAnnotationLanding from "./page";

const TASKS = [
  { id: "t1", document_id: "d1", annotator_user_id: "admin-1", status: "completed", created_at: "", updated_at: null, filename: "Contract-NDA.pdf", span_count: 15 },
  { id: "t2", document_id: "d2", annotator_user_id: "annotator-1", status: "completed", created_at: "", updated_at: null, filename: "Invoice-2024.pdf", span_count: 20 },
  { id: "t3", document_id: "d3", annotator_user_id: "annotator-1", status: "in-progress", created_at: "", updated_at: null, filename: "Q3-Report.pdf", span_count: 4 },
];

function jsonResponse(body: unknown) {
  return new Response(JSON.stringify(body), { status: 200, headers: { "Content-Type": "application/json" } });
}

const mockFetch = vi.fn((input: RequestInfo | URL) => {
  const url = typeof input === "string" ? input : input.toString();
  if (url.includes("/api/v1/annotation-tasks")) return Promise.resolve(jsonResponse(TASKS));
  if (url.includes("/api/v1/documents")) return Promise.resolve(jsonResponse({ documents: [], total: 100, page: 1, per_page: 1 }));
  if (url.includes("/entity-types")) return Promise.resolve(jsonResponse({ entity_types: [] }));
  return Promise.resolve(jsonResponse({}));
});
globalThis.fetch = mockFetch as unknown as typeof fetch;

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("ManualAnnotationLanding", () => {
  beforeEach(() => {
    mockFetch.mockClear();
    mockPush.mockClear();
  });

  it("tenant_admin sees tenant-wide stats and no Review queue card", async () => {
    mockUser = { role: "tenant_admin", userId: "admin-1", tenantSlug: "acme" };
    render(<ManualAnnotationLanding />, { wrapper: createWrapper() });

    expect(await screen.findByText("100")).toBeDefined();
    expect(screen.getByText("documents ready")).toBeDefined();
    expect(await screen.findByText("2")).toBeDefined(); // 2 completed tasks tenant-wide
    expect(screen.getByText("annotated")).toBeDefined();

    expect(screen.queryByText("Review queue")).toBeNull();
    expect(screen.queryByText(/open queue/i)).toBeNull();
  });

  it("tenant_admin sees the three-step workflow in order: upload, define entities, workspace", async () => {
    mockUser = { role: "tenant_admin", userId: "admin-1", tenantSlug: "acme" };
    render(<ManualAnnotationLanding />, { wrapper: createWrapper() });

    expect(await screen.findByText("1. Upload documents")).toBeDefined();
    expect(screen.getByText("2. Define entity types")).toBeDefined();
    expect(screen.getByText("3. Annotation workspace")).toBeDefined();

    fireEvent.click(screen.getByText("Upload documents →"));
    expect(mockPush).toHaveBeenCalledWith("/documents?upload=1");

    fireEvent.click(screen.getByText("Entity types →"));
    expect(mockPush).toHaveBeenCalledWith("/entity-types");

    fireEvent.click(screen.getByText("Open workspace →"));
    expect(mockPush).toHaveBeenCalledWith("/annotation");
  });

  it("annotator sees only the workspace card, not the upload/entity-type steps", async () => {
    mockUser = { role: "annotator", userId: "annotator-1", tenantSlug: "acme" };
    render(<ManualAnnotationLanding />, { wrapper: createWrapper() });

    expect(await screen.findByText("Annotation workspace")).toBeDefined();
    expect(screen.queryByText(/1\. Upload documents/)).toBeNull();
    expect(screen.queryByText(/2\. Define entity types/)).toBeNull();
  });

  it("tenant_admin's Annotated Documents list includes every tenant's completed tasks", async () => {
    mockUser = { role: "tenant_admin", userId: "admin-1", tenantSlug: "acme" };
    render(<ManualAnnotationLanding />, { wrapper: createWrapper() });

    expect(await screen.findByText("Contract-NDA.pdf")).toBeDefined();
    expect(screen.getByText("Invoice-2024.pdf")).toBeDefined();
    expect(screen.queryByText("Q3-Report.pdf")).toBeNull(); // in-progress, not completed
  });

  it("tenant_admin sees the Train model CTA and it routes to /training-jobs", async () => {
    mockUser = { role: "tenant_admin", userId: "admin-1", tenantSlug: "acme" };
    render(<ManualAnnotationLanding />, { wrapper: createWrapper() });

    const cta = await screen.findByText("Train model →");
    fireEvent.click(cta);
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith("/training-jobs?source=manual"));
  });

  it("annotator sees only their own completed count and their own annotated documents", async () => {
    mockUser = { role: "annotator", userId: "annotator-1", tenantSlug: "acme" };
    render(<ManualAnnotationLanding />, { wrapper: createWrapper() });

    expect(screen.getByText("completed by me")).toBeDefined();
    expect(await screen.findByText("Invoice-2024.pdf")).toBeDefined();
    expect(screen.queryByText("Contract-NDA.pdf")).toBeNull(); // belongs to admin-1, not this annotator

    // annotator is never shown the training hand-off
    expect(screen.queryByText("Train model →")).toBeNull();
  });
});
