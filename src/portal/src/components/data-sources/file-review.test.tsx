import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { UploadedFilesSection } from "./uploaded-files";
import { FileReview } from "./file-review";

const mockAuthFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({
  authFetch: (...args: unknown[]) => mockAuthFetch(...args),
}));

function Wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
}

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const FILE = {
  id: "f-1",
  display_name: "sales_q3.csv",
  status: "needs_review",
  served_version: null,
  served: null,
  pending: { version: 1, status: "needs_review", failure_reason: null, sheet: null },
  row_count: 4,
  updated_at: "2026-09-23T10:00:00Z",
};

function profileBody(overrides: Record<string, unknown> = {}) {
  return {
    file: FILE,
    version: 1,
    status: "needs_review",
    failure_reason: null,
    source_filename: "sales_q3.csv",
    sheet: null,
    profile: {
      relation: "sales_q3",
      row_count: 4,
      columns: [
        { index: 0, identifier: "amount", label: "amount", type: "text", date_format: null, date_format_required: false, null_count: 0, distinct_count: 4, warnings: [] },
        { index: 1, identifier: "closed_on", label: "closed_on", type: "date", date_format: null, date_format_required: true, null_count: 0, distinct_count: 3, warnings: [] },
      ],
    },
    review: {
      table: { relation: "sales_q3", description: "", null_tokens: ["", "n/a"] },
      columns: [
        { index: 0, label: "amount", identifier: "amount", type: "text", date_format: null, excluded: false, description: "", value_hints: [] },
        { index: 1, label: "closed_on", identifier: "closed_on", type: "date", date_format: null, excluded: false, description: "", value_hints: [] },
      ],
    },
    load_report: { rows_read: 4, rows_to_load: 4, rows_rejected: 0, rejects: [], preview: [{ amount: "1200" }] },
    blockers: [{ code: "DATE_FORMAT_REQUIRED", column: "closed_on" }, { code: "DESCRIPTION_REQUIRED" }],
    schema_diff: null,
    ...overrides,
  };
}

describe("FileReview", () => {
  beforeEach(() => mockAuthFetch.mockReset());

  it("Review shows blocking reasons", async () => {
    mockAuthFetch.mockImplementation(() => Promise.resolve(json(profileBody())));
    render(<FileReview fileId="f-1" version={1} onClose={() => {}} onPublished={() => {}} />, { wrapper: Wrapper });
    const blocked = await screen.findByRole("region", { name: "Publishing is blocked" });
    expect(blocked).toHaveTextContent("Choose a date format for column “closed_on”.");
    expect(blocked).toHaveTextContent("Add a table description.");
    expect(screen.getByRole("button", { name: "Publish" })).toBeDisabled();
  });

  it("Type change refreshes the load report", async () => {
    const recomputed = profileBody({
      review: {
        ...profileBody().review,
        columns: [{ ...profileBody().review.columns[0], type: "numeric" }, profileBody().review.columns[1]],
      },
      load_report: { rows_read: 4, rows_to_load: 3, rows_rejected: 1, rejects: [{ row: 3, reason: "cast_failed", column: "amount" }], preview: [] },
    });
    mockAuthFetch.mockImplementation((_input: RequestInfo | URL, init?: RequestInit) =>
      Promise.resolve(json(init?.method === "PUT" ? recomputed : profileBody())),
    );
    const user = userEvent.setup();
    render(<FileReview fileId="f-1" version={1} onClose={() => {}} onPublished={() => {}} />, { wrapper: Wrapper });
    expect(await screen.findByTestId("rows-rejected")).toHaveTextContent("0");

    await user.selectOptions(screen.getByLabelText("Type for amount"), "numeric");

    await waitFor(() => expect(screen.getByTestId("rows-rejected")).toHaveTextContent("1"));
    const put = mockAuthFetch.mock.calls.find(([, init]) => (init as RequestInit)?.method === "PUT");
    expect(put?.[0]).toBe("/api/v1/data-sources/files/f-1/versions/1/review");
    expect(JSON.parse((put?.[1] as RequestInit).body as string)).toEqual({ columns: [{ index: 0, type: "numeric" }] });
    expect(screen.getByRole("list", { name: "Rejected rows" })).toHaveTextContent("Row 3: amount");
  });

  it("Successful publish returns to the list", async () => {
    let published = false;
    const ready = { ...FILE, status: "ready", served_version: 1, served: { version: 1, status: "ready", sheet: null }, pending: null };
    mockAuthFetch.mockImplementation((input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url === "/api/v1/data-sources/files") return Promise.resolve(json({ enabled: true, files: [published ? ready : FILE] }));
      if (init?.method === "POST" && url.endsWith("/publish")) {
        published = true;
        return Promise.resolve(json({ file: ready, version: 1, status: "publishing" }, 202));
      }
      return Promise.resolve(json(profileBody({ blockers: [], review: { ...profileBody().review, table: { relation: "sales_q3", description: "Q3", null_tokens: [] } } })));
    });
    const user = userEvent.setup();
    render(<UploadedFilesSection dataPlaneMode="platform" />, { wrapper: Wrapper });
    await user.click(await screen.findByRole("button", { name: "Review v1" }));
    const publish = await screen.findByRole("button", { name: "Publish" });
    expect(publish).toBeEnabled();
    await user.click(publish);

    const entry = await screen.findByTestId("tabular-file-f-1");
    await waitFor(() => expect(within(entry).getByText("Ready")).toBeInTheDocument());
    const post = mockAuthFetch.mock.calls.find(([u, init]) => String(u).endsWith("/publish") && (init as RequestInit)?.method === "POST");
    const key = ((post?.[1] as RequestInit).headers as Record<string, string>)["Idempotency-Key"];
    expect(key).toMatch(/^ds-/);
  });
});
