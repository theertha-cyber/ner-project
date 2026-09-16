import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { ExportCard } from "./ExportCard";

const mockFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({
  authFetch: (url: string) => mockFetch(url),
}));

describe("ExportCard", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    (URL as unknown as { createObjectURL: () => string }).createObjectURL = vi.fn(() => "blob:mock-url");
    (URL as unknown as { revokeObjectURL: () => void }).revokeObjectURL = vi.fn();
  });

  const exportInfo = { message_id: "msg-1", row_count: 250, formats: ["csv", "xlsx"] };
  const singleResult = { message_id: "msg-2", row_count: 1, formats: ["csv", "xlsx"] };

  it("shows a count-stating prompt with no download actions before the user responds", () => {
    render(<ExportCard export_={exportInfo} />);
    expect(screen.getByText(/250 results/)).toBeInTheDocument();
    expect(screen.queryByLabelText("Download CSV")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Download XLSX")).not.toBeInTheDocument();
  });

  it("states the count in singular for a single result", () => {
    render(<ExportCard export_={singleResult} />);
    expect(screen.getByText(/1 result\b/)).toBeInTheDocument();
    expect(screen.queryByText(/1 results/)).not.toBeInTheDocument();
  });

  it("clicking the prompt reveals both format actions in its place", () => {
    render(<ExportCard export_={exportInfo} />);
    fireEvent.click(screen.getByText(/250 results/));
    expect(screen.getByLabelText("Download CSV")).toBeInTheDocument();
    expect(screen.getByLabelText("Download XLSX")).toBeInTheDocument();
    // In-place swap, not additive: the prompt question is gone once revealed.
    expect(screen.queryByText(/want a downloadable version/)).not.toBeInTheDocument();
  });

  it("clicking Download CSV (once revealed) fetches the export endpoint and saves via a blob URL", async () => {
    const blob = new Blob(["a,b\n1,2"], { type: "text/csv" });
    mockFetch.mockResolvedValue({ ok: true, blob: () => Promise.resolve(blob) });

    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    render(<ExportCard export_={exportInfo} />);
    fireEvent.click(screen.getByText(/250 results/));
    fireEvent.click(screen.getByLabelText("Download CSV"));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith("/api/v1/chat/messages/msg-1/export?format=csv");
    });
    expect(URL.createObjectURL).toHaveBeenCalledWith(blob);
    expect(clickSpy).toHaveBeenCalled();
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:mock-url");

    clickSpy.mockRestore();
  });

  it("clicking Download XLSX (once revealed) fetches the export endpoint with format=xlsx", async () => {
    const blob = new Blob([new Uint8Array([1, 2, 3])]);
    mockFetch.mockResolvedValue({ ok: true, blob: () => Promise.resolve(blob) });
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});

    render(<ExportCard export_={exportInfo} />);
    fireEvent.click(screen.getByText(/250 results/));
    fireEvent.click(screen.getByLabelText("Download XLSX"));

    await waitFor(() => {
      expect(mockFetch).toHaveBeenCalledWith("/api/v1/chat/messages/msg-1/export?format=xlsx");
    });
  });

  it("shows an error indicator when the download fails, without throwing", async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500 });

    render(<ExportCard export_={exportInfo} />);
    fireEvent.click(screen.getByText(/250 results/));
    fireEvent.click(screen.getByLabelText("Download CSV"));

    await waitFor(() => {
      expect(screen.getByText("Download failed")).toBeInTheDocument();
    });
  });
});
