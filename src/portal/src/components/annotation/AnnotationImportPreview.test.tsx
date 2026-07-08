import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AnnotationImportPreview } from "./AnnotationImportPreview";

const mockAuthFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({ authFetch: (...args: unknown[]) => mockAuthFetch(...args) }));

const mockUseEntityTypes = vi.fn();
vi.mock("@/hooks/use-entity-types", () => ({
  useEntityTypes: () => mockUseEntityTypes(),
}));

vi.mock("@/components/ui", () => ({
  SlideOver: ({ open, children }: { open: boolean; children: React.ReactNode }) =>
    open ? <div data-testid="slide-over">{children}</div> : null,
  Spinner: ({ size }: { size: string }) => <div data-testid="spinner" />,
}));

function makeQC() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function renderPreview(
  open = true,
  file: File | null = new File(["John\tB-PER\n"], "test.txt", { type: "text/plain" }),
  onConfirm = vi.fn(),
  onClose = vi.fn(),
) {
  return render(
    <QueryClientProvider client={makeQC()}>
      <AnnotationImportPreview
        open={open}
        file={file}
        onConfirm={onConfirm}
        onClose={onClose}
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
  mockUseEntityTypes.mockReturnValue({
    data: { entity_types: [{ name: "PER" }, { name: "ORG" }, { name: "LOC" }] },
  });
});

describe("AnnotationImportPreview", () => {
  it("shows parsing spinner initially", async () => {
    renderPreview();
    expect(screen.getByTestId("spinner")).toBeInTheDocument();
  });

  it("shows parse error for malformed file", async () => {
    const badFile = new File(["John B-PER\n"], "test.txt", { type: "text/plain" });
    renderPreview(true, badFile);
    await waitFor(() => {
      expect(screen.getByText(/expected token and tag separated by tab/i)).toBeInTheDocument();
    });
  });

  it("shows file too large error", async () => {
    const largeContent = "x".repeat(51 * 1024 * 1024);
    const largeFile = new File([largeContent], "large.txt", { type: "text/plain" });
    renderPreview(true, largeFile);
    await waitFor(() => {
      expect(screen.getByText(/File exceeds the 50MB maximum/i)).toBeInTheDocument();
    });
  });

  it("shows valid preview with entity type counts", async () => {
    renderPreview();
    await waitFor(() => {
      expect(screen.getByText("CoNLL")).toBeInTheDocument();
    });
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("PER")).toBeInTheDocument();
  });

  it("shows Cancel and Import buttons for valid file", async () => {
    renderPreview();
    await waitFor(() => {
      expect(screen.getByText(/Import 1 rows/)).toBeInTheDocument();
    });
    expect(screen.getByText("Cancel")).toBeInTheDocument();
  });

  it("calls onConfirm when Import is clicked", async () => {
    const onConfirm = vi.fn();
    const testFile = new File(["John\tB-PER\n"], "test.txt", { type: "text/plain" });
    renderPreview(true, testFile, onConfirm);
    await waitFor(() => {
      expect(screen.getByText(/Import 1 rows/)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText(/Import 1 rows/));
    expect(onConfirm).toHaveBeenCalledWith(testFile);
  });

  it("calls onClose when Cancel is clicked", async () => {
    const onClose = vi.fn();
    renderPreview(true, undefined, vi.fn(), onClose);
    fireEvent.click(screen.getByText("Cancel"));
    expect(onClose).toHaveBeenCalled();
  });
});
