import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AssignTaskForm } from "./AssignTaskForm";

// ── Mocks ──────────────────────────────────────────────────────────────────

const mockAuthFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({ authFetch: (...args: unknown[]) => mockAuthFetch(...args) }));

const mockToast = vi.fn();
vi.mock("@/hooks/use-toast", () => ({ useToast: () => ({ toast: mockToast }) }));

// ── Fixtures ──────────────────────────────────────────────────────────────

const processedDoc = { id: "doc-1", filename: "invoice.pdf", status: "processed", content_type: "application/pdf", file_size: 1024, created_at: "2026-01-01" };
const processedDoc2 = { id: "doc-4", filename: "receipt.pdf", status: "processed", content_type: "application/pdf", file_size: 2048, created_at: "2026-01-04" };
const pendingDoc = { id: "doc-2", filename: "pending.pdf", status: "pending", content_type: "application/pdf", file_size: 512, created_at: "2026-01-02" };
const failedDoc = { id: "doc-3", filename: "failed.pdf", status: "failed", content_type: "application/pdf", file_size: 0, created_at: "2026-01-03" };

const annotatorUser = { id: "u-ann", email: "ann@example.com", role: "annotator", status: "active" };
const adminUser = { id: "u-adm", email: "adm@example.com", role: "tenant_admin", status: "active" };

function makeQC() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function renderForm(onAssign = vi.fn(), onCancel = vi.fn()) {
  return render(
    <QueryClientProvider client={makeQC()}>
      <AssignTaskForm onAssign={onAssign} onCancel={onCancel} />
    </QueryClientProvider>,
  );
}

// ── Setup ──────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
  // Default: return documents (processed x2 + pending + failed) and users (admin + annotator)
  mockAuthFetch.mockImplementation((url: string) => {
    if (url.includes("/api/v1/documents")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ documents: [processedDoc, processedDoc2, pendingDoc, failedDoc], total: 4, page: 1, per_page: 200 }),
      });
    }
    if (url.includes("/api/v1/users")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve([annotatorUser, adminUser]),
      });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
  });
});

// ── Scenario 4: Document list shows only processed documents ───────────────

describe("Scenario 4 — Document list shows only processed documents", () => {
  it("includes only processed documents; excludes pending and failed", async () => {
    renderForm();

    await waitFor(() => {
      expect(screen.getByTestId("document-checkbox-list")).toBeInTheDocument();
    });

    const list = screen.getByTestId("document-checkbox-list");
    expect(within(list).getByText("invoice.pdf")).toBeInTheDocument();
    expect(within(list).getByText("receipt.pdf")).toBeInTheDocument();
    expect(within(list).queryByText("pending.pdf")).toBeNull();
    expect(within(list).queryByText("failed.pdf")).toBeNull();
  });
});

// ── Scenario 5: Annotator dropdown shows only annotator-role users ─────────

describe("Scenario 5 — Annotator dropdown shows only annotator-role users", () => {
  it("shows annotator-role users and excludes tenant_admin users", async () => {
    renderForm();

    await waitFor(() => {
      expect(screen.getByTestId("annotator-select")).toBeInTheDocument();
    });

    const select = screen.getByTestId("annotator-select");
    expect(select).toHaveTextContent("ann@example.com");
    expect(select).not.toHaveTextContent("adm@example.com");
  });
});

// ── Scenario 6: Assign button disabled until at least one document and an annotator are selected

describe("Scenario 6 — Assign button disabled until fields selected", () => {
  it("is disabled initially", async () => {
    renderForm();
    await waitFor(() => expect(screen.getByTestId("document-checkbox-list")).toBeInTheDocument());
    expect(screen.getByTestId("assign-submit-btn")).toBeDisabled();
  });

  it("is disabled when only a document is checked", async () => {
    renderForm();
    await waitFor(() => expect(screen.getByTestId("document-checkbox-list")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("document-checkbox-doc-1"));
    expect(screen.getByTestId("assign-submit-btn")).toBeDisabled();
  });

  it("is disabled when only annotator is selected", async () => {
    renderForm();
    await waitFor(() => expect(screen.getByTestId("annotator-select")).toBeInTheDocument());
    fireEvent.change(screen.getByTestId("annotator-select"), { target: { value: "u-ann" } });
    expect(screen.getByTestId("assign-submit-btn")).toBeDisabled();
  });

  it("is enabled when one document and annotator are selected", async () => {
    renderForm();
    await waitFor(() => expect(screen.getByTestId("document-checkbox-list")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("document-checkbox-doc-1"));
    fireEvent.change(screen.getByTestId("annotator-select"), { target: { value: "u-ann" } });
    expect(screen.getByTestId("assign-submit-btn")).not.toBeDisabled();
  });

  it("is enabled when multiple documents are checked", async () => {
    renderForm();
    await waitFor(() => expect(screen.getByTestId("document-checkbox-list")).toBeInTheDocument());
    fireEvent.click(screen.getByTestId("document-checkbox-doc-1"));
    fireEvent.click(screen.getByTestId("document-checkbox-doc-4"));
    fireEvent.change(screen.getByTestId("annotator-select"), { target: { value: "u-ann" } });
    expect(screen.getByTestId("assign-submit-btn")).not.toBeDisabled();
    expect(screen.getByTestId("assign-submit-btn")).toHaveTextContent("Assign 2 documents");
  });
});

// ── Select all / Clear ──────────────────────────────────────────────────────

describe("Select all / Clear controls", () => {
  it("selects every processed document and reports the count", async () => {
    renderForm();
    await waitFor(() => expect(screen.getByTestId("document-checkbox-list")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("select-all-documents-btn"));

    expect(screen.getByTestId("document-checkbox-doc-1")).toBeChecked();
    expect(screen.getByTestId("document-checkbox-doc-4")).toBeChecked();
    expect(screen.getByText("Documents (2 selected)")).toBeInTheDocument();
  });

  it("clears every selected document", async () => {
    renderForm();
    await waitFor(() => expect(screen.getByTestId("document-checkbox-list")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("select-all-documents-btn"));
    fireEvent.click(screen.getByTestId("clear-documents-btn"));

    expect(screen.getByTestId("document-checkbox-doc-1")).not.toBeChecked();
    expect(screen.getByTestId("document-checkbox-doc-4")).not.toBeChecked();
  });
});

// ── Scenario 7: Successful task creation ────────────────────────────────────

describe("Scenario 7 — Successful task creation adds task(s) to the queue", () => {
  it("calls onAssign with the new task and shows toast on 201 for a single document", async () => {
    const newTask = {
      id: "task-new",
      document_id: "doc-1",
      annotator_user_id: "u-ann",
      status: "unannotated",
      created_at: "2026-01-10",
      updated_at: null,
      filename: "invoice.pdf",
    };

    mockAuthFetch.mockImplementation((url: string) => {
      if (url.includes("/api/v1/documents")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ documents: [processedDoc], total: 1, page: 1, per_page: 200 }) });
      }
      if (url.includes("/api/v1/users")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([annotatorUser]) });
      }
      if (url === "/api/v1/annotation-tasks") {
        return Promise.resolve({ ok: true, status: 201, json: () => Promise.resolve(newTask) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    const onAssign = vi.fn();
    renderForm(onAssign);

    await waitFor(() => expect(screen.getByTestId("document-checkbox-list")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("document-checkbox-doc-1"));
    fireEvent.change(screen.getByTestId("annotator-select"), { target: { value: "u-ann" } });
    fireEvent.click(screen.getByTestId("assign-submit-btn"));

    await waitFor(() => expect(onAssign).toHaveBeenCalledWith([newTask]));
    expect(mockToast).toHaveBeenCalledWith("Task assigned successfully", "ok");
  });

  it("creates one task per selected document and closes with all of them when every one succeeds", async () => {
    let callCount = 0;
    mockAuthFetch.mockImplementation((url: string, init?: RequestInit) => {
      if (url.includes("/api/v1/documents")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ documents: [processedDoc, processedDoc2], total: 2, page: 1, per_page: 200 }) });
      }
      if (url.includes("/api/v1/users")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([annotatorUser]) });
      }
      if (url === "/api/v1/annotation-tasks" && init?.method === "POST") {
        callCount += 1;
        const body = JSON.parse(init.body as string);
        return Promise.resolve({
          ok: true,
          status: 201,
          json: () => Promise.resolve({ id: `task-${callCount}`, document_id: body.document_id, annotator_user_id: body.annotator_user_id, status: "unannotated" }),
        });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    const onAssign = vi.fn();
    renderForm(onAssign);

    await waitFor(() => expect(screen.getByTestId("document-checkbox-list")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("select-all-documents-btn"));
    fireEvent.change(screen.getByTestId("annotator-select"), { target: { value: "u-ann" } });
    fireEvent.click(screen.getByTestId("assign-submit-btn"));

    await waitFor(() => expect(onAssign).toHaveBeenCalled());
    expect(onAssign.mock.calls[0][0]).toHaveLength(2);
    expect(mockToast).toHaveBeenCalledWith("2 tasks assigned successfully", "ok");
    expect(callCount).toBe(2);
  });
});

// ── Scenario 8: A per-document conflict is shown without closing the form ──

describe("Scenario 8 — Per-document failures are shown and keep the form open", () => {
  it("shows the conflict for a single selected document and does not call onAssign", async () => {
    mockAuthFetch.mockImplementation((url: string) => {
      if (url.includes("/api/v1/documents")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ documents: [processedDoc], total: 1, page: 1, per_page: 200 }) });
      }
      if (url.includes("/api/v1/users")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([annotatorUser]) });
      }
      if (url === "/api/v1/annotation-tasks") {
        return Promise.resolve({ ok: false, status: 409, json: () => Promise.resolve({ detail: "conflict" }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    const onAssign = vi.fn();
    renderForm(onAssign);

    await waitFor(() => expect(screen.getByTestId("document-checkbox-list")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("document-checkbox-doc-1"));
    fireEvent.change(screen.getByTestId("annotator-select"), { target: { value: "u-ann" } });
    fireEvent.click(screen.getByTestId("assign-submit-btn"));

    await waitFor(() => expect(screen.getByTestId("assign-result-doc-1")).toBeInTheDocument());

    expect(screen.getByTestId("assign-result-doc-1")).toHaveTextContent("Already has an active task");
    expect(screen.getByTestId("assign-task-form")).toBeInTheDocument();
    expect(onAssign).not.toHaveBeenCalled();
  });

  it("reports a mixed batch (one success, one conflict) and only closes once Done is clicked", async () => {
    mockAuthFetch.mockImplementation((url: string, init?: RequestInit) => {
      if (url.includes("/api/v1/documents")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ documents: [processedDoc, processedDoc2], total: 2, page: 1, per_page: 200 }) });
      }
      if (url.includes("/api/v1/users")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve([annotatorUser]) });
      }
      if (url === "/api/v1/annotation-tasks" && init?.method === "POST") {
        const body = JSON.parse(init.body as string);
        if (body.document_id === "doc-1") {
          return Promise.resolve({
            ok: true,
            status: 201,
            json: () => Promise.resolve({ id: "task-1", document_id: "doc-1", annotator_user_id: "u-ann", status: "unannotated" }),
          });
        }
        return Promise.resolve({ ok: false, status: 409, json: () => Promise.resolve({ detail: "conflict" }) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    const onAssign = vi.fn();
    renderForm(onAssign);

    await waitFor(() => expect(screen.getByTestId("document-checkbox-list")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("select-all-documents-btn"));
    fireEvent.change(screen.getByTestId("annotator-select"), { target: { value: "u-ann" } });
    fireEvent.click(screen.getByTestId("assign-submit-btn"));

    await waitFor(() => expect(screen.getByTestId("assign-results")).toBeInTheDocument());
    expect(screen.getByTestId("assign-result-doc-1")).toHaveTextContent("assigned");
    expect(screen.getByTestId("assign-result-doc-4")).toHaveTextContent("Already has an active task");
    expect(onAssign).not.toHaveBeenCalled();
    expect(mockToast).toHaveBeenCalledWith("1 of 2 tasks assigned", "ok");

    fireEvent.click(screen.getByTestId("assign-done-btn"));
    expect(onAssign).toHaveBeenCalledWith([
      expect.objectContaining({ id: "task-1", document_id: "doc-1" }),
    ]);
  });
});

// ── Scenario 9: Cancel collapses form, no POST sent ───────────────────────

describe("Scenario 9 — Cancel collapses form without submitting", () => {
  it("calls onCancel and does not send a POST request", async () => {
    const onCancel = vi.fn();
    renderForm(vi.fn(), onCancel);

    await waitFor(() => {
      expect(screen.getByTestId("assign-task-form")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("assign-cancel-btn"));

    expect(onCancel).toHaveBeenCalled();
    const postCall = mockAuthFetch.mock.calls.find(
      (args) => args[0] === "/api/v1/annotation-tasks" && (args[1] as RequestInit | undefined)?.method === "POST",
    );
    expect(postCall).toBeUndefined();
  });
});

// ── Scenario 10: Empty annotator list shows descriptive message ────────────

describe("Scenario 10 — Empty annotator list shows descriptive message", () => {
  it("shows 'No annotators available' message and disables Assign button", async () => {
    mockAuthFetch.mockImplementation((url: string) => {
      if (url.includes("/api/v1/documents")) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ documents: [processedDoc], total: 1, page: 1, per_page: 200 }) });
      }
      if (url.includes("/api/v1/users")) {
        // No annotator-role users
        return Promise.resolve({ ok: true, json: () => Promise.resolve([adminUser]) });
      }
      return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
    });

    renderForm();

    await waitFor(() => {
      expect(screen.getByTestId("no-annotators-message")).toBeInTheDocument();
    });

    expect(screen.getByTestId("no-annotators-message")).toHaveTextContent(
      "No annotators available — invite users first",
    );
    expect(screen.getByTestId("assign-submit-btn")).toBeDisabled();
  });
});
