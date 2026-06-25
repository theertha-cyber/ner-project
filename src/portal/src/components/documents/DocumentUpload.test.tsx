import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DocumentUpload } from "./DocumentUpload";

vi.mock("@/hooks/use-upload", () => ({
  useUpload: vi.fn(() => ({
    upload: vi.fn().mockResolvedValue(undefined),
    progress: 0,
    isUploading: false,
    error: null,
    reset: vi.fn(),
  })),
}));

vi.mock("@/lib/auth", () => ({
  useAuth: vi.fn(() => ({
    getAccessToken: vi.fn(() => "mock-token"),
  })),
}));

function createWrapper() {
  const qc = new QueryClient();
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

function createFile(name: string, type: string, size: number): File {
  const blob = new Blob([new ArrayBuffer(size)], { type });
  return new File([blob], name, { type });
}

describe("DocumentUpload", () => {
  it("renders upload zone with instructions", () => {
    render(<DocumentUpload />, { wrapper: createWrapper() });
    expect(screen.getByText(/Click to upload/)).toBeDefined();
    expect(screen.getByText(/PDF, JPEG, PNG, or TIFF/)).toBeDefined();
  });

  it("shows inline error for unsupported file type on drop", () => {
    render(<DocumentUpload />, { wrapper: createWrapper() });
    const zone = screen.getByText(/Click to upload/).closest("div")!;
    const exeFile = createFile("malware.exe", "application/x-msdownload", 1000);
    fireEvent.drop(zone, { dataTransfer: { files: [exeFile] } });
    expect(screen.getByRole("alert")).toHaveTextContent(/not supported/);
  });

  it("shows inline error for oversized file on drop", () => {
    render(<DocumentUpload />, { wrapper: createWrapper() });
    const zone = screen.getByText(/Click to upload/).closest("div")!;
    const bigFile = createFile("large.pdf", "application/pdf", 60 * 1024 * 1024);
    fireEvent.drop(zone, { dataTransfer: { files: [bigFile] } });
    expect(screen.getByRole("alert")).toHaveTextContent(/exceeds/);
  });

  it("shows highlighted state on drag over", () => {
    render(<DocumentUpload />, { wrapper: createWrapper() });
    const zone = screen.getByText(/Click to upload/).closest("div")!;
    fireEvent.dragOver(zone);
    expect(zone.className).toContain("border-brand-primary");
  });

  it("resets visual state on drag leave", () => {
    render(<DocumentUpload />, { wrapper: createWrapper() });
    const zone = screen.getByText(/Click to upload/).closest("div")!;
    fireEvent.dragOver(zone);
    expect(zone.className).toContain("border-brand-primary");
    fireEvent.dragLeave(zone);
    expect(zone.className).not.toContain("border-brand-primary");
  });
});
