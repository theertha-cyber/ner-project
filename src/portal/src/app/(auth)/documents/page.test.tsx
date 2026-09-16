import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";

const mockPush = vi.fn();
const mockReplace = vi.fn();
let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: mockPush, replace: mockReplace })),
  useSearchParams: vi.fn(() => mockSearchParams),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(() => ({ user: { role: "tenant_admin", tenantId: "t1", userId: "u1", email: "a@b.com", tenantSlug: "acme" } })),
}));

vi.mock("@/hooks/use-documents", () => ({
  useDocuments: vi.fn(() => ({ data: { documents: [], total: 0, page: 1, per_page: 25 }, isLoading: false })),
}));

vi.mock("@/components/documents/DocumentTable", () => ({
  DocumentTable: () => <div />,
}));

const mockUploadDialog = vi.fn();
vi.mock("@/components/documents/UploadDialog", () => ({
  UploadDialog: (props: { open: boolean; purpose?: string; defaultAnnotationMode?: string }) => {
    mockUploadDialog(props);
    return props.open ? <div data-testid="upload-dialog-open" /> : null;
  },
}));

import DocumentsPage from "./page";

describe("DocumentsPage", () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockReplace.mockClear();
    mockUploadDialog.mockClear();
    mockSearchParams = new URLSearchParams();
  });

  it("keeps the uploader closed by default", () => {
    render(<DocumentsPage />);
    expect(screen.queryByTestId("upload-dialog-open")).toBeNull();
  });

  it("auto-opens the uploader when linked with ?upload=1", () => {
    mockSearchParams = new URLSearchParams("upload=1");
    render(<DocumentsPage />);
    expect(screen.getByTestId("upload-dialog-open")).toBeDefined();
  });

  it("does not auto-open the uploader for an unrelated query param", () => {
    mockSearchParams = new URLSearchParams("status=processed");
    render(<DocumentsPage />);
    expect(screen.queryByTestId("upload-dialog-open")).toBeNull();
  });

  it("opens the uploader pre-set to qa_pair when linked with ?upload=1&purpose=qa_pair", () => {
    mockSearchParams = new URLSearchParams("upload=1&purpose=qa_pair");
    render(<DocumentsPage />);
    expect(screen.getByTestId("upload-dialog-open")).toBeDefined();
    const lastCall = mockUploadDialog.mock.calls.at(-1)![0];
    expect(lastCall.purpose).toBe("qa_pair");
  });

  it("opens the uploader pre-set to Automated when linked with ?upload=1&purpose=training&mode=automated", () => {
    mockSearchParams = new URLSearchParams("upload=1&purpose=training&mode=automated");
    render(<DocumentsPage />);
    expect(screen.getByTestId("upload-dialog-open")).toBeDefined();
    const lastCall = mockUploadDialog.mock.calls.at(-1)![0];
    expect(lastCall.purpose).toBe("training");
    expect(lastCall.defaultAnnotationMode).toBe("automated");
  });
});
