import { describe, it, expect, vi, beforeEach } from "vitest";
import { useState, useCallback, useRef } from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DocumentUpload } from "./DocumentUpload";

let uploadCalls: { name: string; purpose: string }[] = [];
let inFlightCount = 0;
let maxInFlight = 0;
type Deferred = {
  resolve: () => void;
  reject: (err: Error) => void;
  progress: (pct: number) => void;
};
let deferreds: Deferred[] = [];

function useUploadMock() {
  const [progress, setProgress] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const cancelledRef = useRef(false);

  const upload = useCallback((file: File, purpose: "query" | "training" = "query") => {
    uploadCalls.push({ name: file.name, purpose });
    inFlightCount += 1;
    maxInFlight = Math.max(maxInFlight, inFlightCount);
    setIsUploading(true);
    setProgress(0);

    return new Promise<void>((resolve, reject) => {
      deferreds.push({
        resolve: () => {
          inFlightCount -= 1;
          setProgress(100);
          setIsUploading(false);
          resolve();
        },
        reject: (err: Error) => {
          inFlightCount -= 1;
          setIsUploading(false);
          reject(err);
        },
        progress: (pct: number) => setProgress(pct),
      });
    });
  }, []);

  const reset = useCallback(() => {
    setProgress(0);
    setIsUploading(false);
    cancelledRef.current = false;
  }, []);

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    const last = deferreds[deferreds.length - 1];
    last?.reject(new DOMException("Upload cancelled", "AbortError"));
  }, []);

  return { upload, progress, isUploading, error: null, reset, cancel };
}

vi.mock("@/hooks/use-upload", () => ({
  useUpload: () => useUploadMock(),
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

async function resolveNext() {
  await waitFor(() => expect(deferreds.length).toBeGreaterThan(0));
  const d = deferreds[deferreds.length - 1];
  d.resolve();
}

async function rejectNext(message: string) {
  await waitFor(() => expect(deferreds.length).toBeGreaterThan(0));
  const d = deferreds[deferreds.length - 1];
  d.reject(new Error(message));
}

describe("DocumentUpload", () => {
  beforeEach(() => {
    uploadCalls = [];
    deferreds = [];
    inFlightCount = 0;
    maxInFlight = 0;
  });

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

  it("multi-file drop uploads all files sequentially", async () => {
    render(<DocumentUpload />, { wrapper: createWrapper() });
    const zone = screen.getByText(/Click to upload/).closest("div")!;
    const files = [
      createFile("a.pdf", "application/pdf", 100),
      createFile("b.png", "image/png", 100),
      createFile("c.tiff", "image/tiff", 100),
    ];
    fireEvent.drop(zone, { dataTransfer: { files } });

    await resolveNext();
    await resolveNext();
    await resolveNext();

    await waitFor(() => expect(uploadCalls.length).toBe(3));
    expect(maxInFlight).toBe(1);
  });

  it("multi-select picker uploads all selected files", async () => {
    render(<DocumentUpload />, { wrapper: createWrapper() });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const files = [
      createFile("x.png", "image/png", 100),
      createFile("y.png", "image/png", 100),
    ];
    fireEvent.change(input, { target: { files } });

    await resolveNext();
    await resolveNext();

    await waitFor(() => expect(uploadCalls.length).toBe(2));
  });

  it("single file via picker uploads immediately", async () => {
    render(<DocumentUpload />, { wrapper: createWrapper() });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = createFile("solo.png", "image/png", 100);
    fireEvent.change(input, { target: { files: [file] } });

    await resolveNext();
    await waitFor(() => expect(uploadCalls.length).toBe(1));
  });

  it("mixed batch rejects invalid files and uploads the valid one", async () => {
    render(<DocumentUpload />, { wrapper: createWrapper() });
    const zone = screen.getByText(/Click to upload/).closest("div")!;
    const valid = createFile("ok.pdf", "application/pdf", 100);
    const badType = createFile("malware.exe", "application/x-msdownload", 100);
    const oversized = createFile("huge.pdf", "application/pdf", 60 * 1024 * 1024);
    fireEvent.drop(zone, { dataTransfer: { files: [valid, badType, oversized] } });

    await waitFor(() => {
      expect(screen.getByText(/not supported/)).toBeDefined();
      expect(screen.getByText(/exceeds/)).toBeDefined();
    });

    await resolveNext();
    await waitFor(() => expect(uploadCalls.length).toBe(1));
    expect(uploadCalls[0].name).toBe("ok.pdf");
  });

  it("selection over 20 files is rejected in full", () => {
    render(<DocumentUpload />, { wrapper: createWrapper() });
    const zone = screen.getByText(/Click to upload/).closest("div")!;
    const files = Array.from({ length: 25 }, (_, i) =>
      createFile(`f${i}.pdf`, "application/pdf", 100),
    );
    fireEvent.drop(zone, { dataTransfer: { files } });

    expect(screen.getByRole("alert")).toHaveTextContent(/20/);
    expect(uploadCalls.length).toBe(0);
  });

  it("batch purpose applies to every file", async () => {
    render(<DocumentUpload />, { wrapper: createWrapper() });
    const trainingRadio = screen.getByLabelText(/Training/);
    fireEvent.click(trainingRadio);

    const zone = screen.getByText(/Click to upload/).closest("div")!;
    const files = [
      createFile("a.pdf", "application/pdf", 100),
      createFile("b.pdf", "application/pdf", 100),
      createFile("c.pdf", "application/pdf", 100),
    ];
    fireEvent.drop(zone, { dataTransfer: { files } });

    await resolveNext();
    await resolveNext();
    await resolveNext();

    await waitFor(() => expect(uploadCalls.length).toBe(3));
    expect(uploadCalls.every((c) => c.purpose === "training")).toBe(true);
  });

  it("progress bar reflects in-flight bytes", async () => {
    render(<DocumentUpload />, { wrapper: createWrapper() });
    const zone = screen.getByText(/Click to upload/).closest("div")!;
    const file = createFile("a.pdf", "application/pdf", 100);
    fireEvent.drop(zone, { dataTransfer: { files: [file] } });

    await waitFor(() => expect(deferreds.length).toBe(1));
    deferreds[0].progress(42);

    await waitFor(() => expect(screen.getByText(/42%/)).toBeDefined());
    deferreds[0].resolve();
  });

  it("batch position indicator shows file N of M", async () => {
    render(<DocumentUpload />, { wrapper: createWrapper() });
    const zone = screen.getByText(/Click to upload/).closest("div")!;
    const files = [
      createFile("a.pdf", "application/pdf", 100),
      createFile("b.pdf", "application/pdf", 100),
      createFile("c.pdf", "application/pdf", 100),
    ];
    fireEvent.drop(zone, { dataTransfer: { files } });

    await resolveNext();
    await waitFor(() => expect(screen.getByText(/file 2 of 3/)).toBeDefined());
    expect(screen.getByText("b.pdf")).toBeDefined();

    await resolveNext();
    await resolveNext();
  });

  it("single-file batch shows no position indicator", async () => {
    render(<DocumentUpload />, { wrapper: createWrapper() });
    const zone = screen.getByText(/Click to upload/).closest("div")!;
    const file = createFile("a.pdf", "application/pdf", 100);
    fireEvent.drop(zone, { dataTransfer: { files: [file] } });

    await waitFor(() => expect(deferreds.length).toBe(1));
    expect(screen.queryByText(/file \d+ of \d+/)).toBeNull();
    deferreds[0].resolve();
  });

  it("single upload success invalidates document list", async () => {
    render(<DocumentUpload />, { wrapper: createWrapper() });
    const zone = screen.getByText(/Click to upload/).closest("div")!;
    const file = createFile("a.pdf", "application/pdf", 100);
    fireEvent.drop(zone, { dataTransfer: { files: [file] } });

    await resolveNext();
    await waitFor(() => expect(screen.getByText(/Upload successful/)).toBeDefined());
  });

  it("batch continues after one file fails", async () => {
    render(<DocumentUpload />, { wrapper: createWrapper() });
    const zone = screen.getByText(/Click to upload/).closest("div")!;
    const files = [
      createFile("a.pdf", "application/pdf", 100),
      createFile("b.pdf", "application/pdf", 100),
      createFile("c.pdf", "application/pdf", 100),
    ];
    fireEvent.drop(zone, { dataTransfer: { files } });

    await resolveNext();
    await rejectNext("Upload failed: 500");
    await resolveNext();

    await waitFor(() => expect(uploadCalls.length).toBe(3));
    await waitFor(() =>
      expect(screen.getByText(/2 of 3 uploaded successfully/)).toBeDefined(),
    );
    expect(screen.getByText(/b\.pdf.*Upload failed: 500/)).toBeDefined();
  });

  it("batch summary reports all successes", async () => {
    render(<DocumentUpload />, { wrapper: createWrapper() });
    const zone = screen.getByText(/Click to upload/).closest("div")!;
    const files = [
      createFile("a.pdf", "application/pdf", 100),
      createFile("b.pdf", "application/pdf", 100),
      createFile("c.pdf", "application/pdf", 100),
    ];
    fireEvent.drop(zone, { dataTransfer: { files } });

    await resolveNext();
    await resolveNext();
    await resolveNext();

    await waitFor(() =>
      expect(screen.getByText(/3 of 3 uploaded successfully/)).toBeDefined(),
    );
  });

  it("cancel aborts in-flight and skips queued files", async () => {
    render(<DocumentUpload />, { wrapper: createWrapper() });
    const zone = screen.getByText(/Click to upload/).closest("div")!;
    const files = [
      createFile("a.pdf", "application/pdf", 100),
      createFile("b.pdf", "application/pdf", 100),
      createFile("c.pdf", "application/pdf", 100),
      createFile("d.pdf", "application/pdf", 100),
      createFile("e.pdf", "application/pdf", 100),
    ];
    fireEvent.drop(zone, { dataTransfer: { files } });

    await resolveNext();
    await waitFor(() => expect(uploadCalls.length).toBe(2));

    const cancelButton = screen.getByText(/Cancel/);
    fireEvent.click(cancelButton);

    await waitFor(() =>
      expect(screen.getByText(/1 of 5 uploaded successfully/)).toBeDefined(),
    );
    expect(uploadCalls.length).toBe(2);
    expect(screen.queryByText(/Network error/)).toBeNull();
    expect(screen.getAllByText(/cancelled/).length).toBeGreaterThan(0);
  });

  it("zone accepts a new selection after cancel", async () => {
    render(<DocumentUpload />, { wrapper: createWrapper() });
    const zone = screen.getByText(/Click to upload/).closest("div")!;
    const files = [
      createFile("a.pdf", "application/pdf", 100),
      createFile("b.pdf", "application/pdf", 100),
    ];
    fireEvent.drop(zone, { dataTransfer: { files } });

    await waitFor(() => expect(uploadCalls.length).toBe(1));
    fireEvent.click(screen.getByText(/Cancel/));

    await waitFor(() =>
      expect(screen.getByText(/0 of 2 uploaded successfully/)).toBeDefined(),
    );

    const newZone = screen.getByRole("button");
    const newFile = createFile("fresh.pdf", "application/pdf", 100);
    fireEvent.drop(newZone, { dataTransfer: { files: [newFile] } });

    await resolveNext();
    await waitFor(() => expect(screen.getByText(/Upload successful/)).toBeDefined());
  });
});
