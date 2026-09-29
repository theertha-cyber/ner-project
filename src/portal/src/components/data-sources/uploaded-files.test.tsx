import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { UploadedFilesSection } from "./uploaded-files";

const mockAuthFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({
  authFetch: (...args: unknown[]) => mockAuthFetch(...args),
}));

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

const SALES = {
  id: "f-1",
  display_name: "sales_q3.csv",
  status: "ready",
  served_version: 1,
  served: { version: 1, status: "ready", sheet: null, published_at: "2026-09-23T10:00:00Z" },
  pending: null,
  row_count: 4,
  updated_at: "2026-09-23T10:00:00Z",
};
const TARGETS = {
  id: "f-2",
  display_name: "targets.csv",
  status: "needs_review",
  served_version: null,
  served: null,
  pending: { version: 1, status: "needs_review", failure_reason: null, sheet: null },
  row_count: 12,
  updated_at: "2026-09-23T11:00:00Z",
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

function serve(files: unknown[], handlers: Record<string, () => Response> = {}) {
  mockAuthFetch.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    const handler = handlers[`${method} ${url}`];
    if (handler) return Promise.resolve(handler());
    if (method === "GET" && url === "/api/v1/data-sources/files") return Promise.resolve(json({ enabled: true, files }));
    return Promise.resolve(json({ error: { code: "INTERNAL_ERROR", message: "x", request_id: "r" } }, 500));
  });
}

describe("UploadedFilesSection", () => {
  beforeEach(() => mockAuthFetch.mockReset());

  it("Administrator sees uploaded files", async () => {
    serve([SALES, TARGETS]);
    render(<UploadedFilesSection dataPlaneMode="platform" />, { wrapper: Wrapper });
    const list = await screen.findByRole("list", { name: "Uploaded files" });
    const sales = within(list).getByTestId("tabular-file-f-1");
    expect(within(sales).getByText("sales_q3.csv")).toBeInTheDocument();
    expect(within(sales).getByText("Ready")).toBeInTheDocument();
    const targets = within(list).getByTestId("tabular-file-f-2");
    expect(within(targets).getByText("Needs review")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Uploaded files" })).toBeInTheDocument();
    expect(screen.queryByTestId("tabular-residency-notice")).not.toBeInTheDocument();
  });

  it("Pending version shown alongside served version", async () => {
    serve([{ ...SALES, pending: { version: 2, status: "needs_review", failure_reason: null, sheet: null } }]);
    render(<UploadedFilesSection dataPlaneMode="platform" />, { wrapper: Wrapper });
    const entry = await screen.findByTestId("tabular-file-f-1");
    expect(entry).toHaveTextContent("v1 served");
    expect(entry).toHaveTextContent("v2 pending");
    expect(within(entry).getByText("Needs review")).toBeInTheDocument();
    expect(within(entry).getByRole("button", { name: "Review v2" })).toBeInTheDocument();
  });

  it("Unsupported file is refused with a fixed message", async () => {
    serve([], {
      "POST /api/v1/data-sources/files": () =>
        json({ error: { code: "UNSUPPORTED_FILE_TYPE", message: "server text never shown", request_id: "r" } }, 415),
    });
    const user = userEvent.setup({ applyAccept: false });
    render(<UploadedFilesSection dataPlaneMode="platform" />, { wrapper: Wrapper });
    await screen.findByText("No uploaded files yet.");
    // A renamed macro workbook passes the client check; the server's code decides.
    const input = screen.getByLabelText("Choose a spreadsheet to upload");
    await user.upload(input, new File(["PK"], "budget.csv", { type: "text/csv" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Only .csv and .xlsx files can be uploaded.");
    expect(alert).not.toHaveTextContent("server text never shown");
    expect(screen.queryByRole("list", { name: "Uploaded files" })).not.toBeInTheDocument();

    // The client refuses an obviously unsupported extension without a request.
    const calls = mockAuthFetch.mock.calls.length;
    await user.upload(input, new File(["x"], "budget.xlsm"));
    expect(mockAuthFetch.mock.calls.length).toBe(calls);
    expect(screen.getByRole("alert")).toHaveTextContent("Only .csv and .xlsx files can be uploaded.");
  });

  it("Delete requires confirmation", async () => {
    serve([SALES], { "DELETE /api/v1/data-sources/files/f-1": () => json({ id: "f-1", status: "deleted" }) });
    const user = userEvent.setup();
    render(<UploadedFilesSection dataPlaneMode="platform" />, { wrapper: Wrapper });
    await user.click(await screen.findByRole("button", { name: "Delete sales_q3.csv" }));
    const dialog = screen.getByRole("dialog");
    expect(dialog).toHaveTextContent("Delete sales_q3.csv?");
    expect(dialog).toHaveTextContent("Chat will stop using sales_q3.csv immediately");
    expect(mockAuthFetch.mock.calls.some(([, init]) => (init as RequestInit)?.method === "DELETE")).toBe(false);

    await user.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(mockAuthFetch.mock.calls.some(([, init]) => (init as RequestInit)?.method === "DELETE")).toBe(false);

    await user.click(screen.getByRole("button", { name: "Delete sales_q3.csv" }));
    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Delete file" }));
    await waitFor(() => {
      const call = mockAuthFetch.mock.calls.find(([, init]) => (init as RequestInit)?.method === "DELETE");
      expect(call?.[0]).toBe("/api/v1/data-sources/files/f-1");
      expect(((call?.[1] as RequestInit).headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
    });
  });

  it("shows the residency notice to tenant_owned tenants", async () => {
    serve([]);
    render(<UploadedFilesSection dataPlaneMode="tenant_owned" />, { wrapper: Wrapper });
    expect(await screen.findByTestId("tabular-residency-notice")).toHaveTextContent("platform's object storage");
  });

  it("is hidden when the kill switch is off", async () => {
    mockAuthFetch.mockResolvedValue(json({ enabled: false, files: [] }));
    const { container } = render(<UploadedFilesSection dataPlaneMode="platform" />, { wrapper: Wrapper });
    await waitFor(() => expect(mockAuthFetch).toHaveBeenCalled());
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });
});
