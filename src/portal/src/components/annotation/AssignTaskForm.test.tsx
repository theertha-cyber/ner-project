import { render, screen, fireEvent, waitFor } from "@testing-library/react";
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
  // Default: return documents (processed + pending + failed) and users (admin + annotator)
  mockAuthFetch.mockImplementation((url: string) => {
    if (url.includes("/api/v1/documents")) {
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({ documents: [processedDoc, pendingDoc, failedDoc], total: 3, page: 1, per_page: 200 }),
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

// ── Scenario 4: Document dropdown shows only processed documents ───────────

describe("Scenario 4 — Document dropdown shows only processed documents", () => {
  it("includes only processed documents; excludes pending and failed", async () => {
    renderForm();

    await waitFor(() => {
      expect(screen.getByTestId("document-select")).toBeInTheDocument();
    });

    const select = screen.getByTestId("document-select");
    expect(select).toHaveTextContent("invoice.pdf");
    expect(select).not.toHaveTextContent("pending.pdf");
    expect(select).not.toHaveTextContent("failed.pdf");
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

// ── Scenario 6: Assign button disabled until both fields selected ──────────

describe("Scenario 6 — Assign button disabled until both fields selected", () => {
  it("is disabled initially", async () => {
    renderForm();

    await waitFor(() => {
      expect(screen.getByTestId("document-select")).toBeInTheDocument();
    });

    expect(screen.getByTestId("assign-submit-btn")).toBeDisabled();
  });

  it("is disabled when only document is selected", async () => {
    renderForm();

    await waitFor(() => {
      expect(screen.getByTestId("document-select")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("document-select"), { target: { value: "doc-1" } });
    expect(screen.getByTestId("assign-submit-btn")).toBeDisabled();
  });

  it("is disabled when only annotator is selected", async () => {
    renderForm();

    await waitFor(() => {
      expect(screen.getByTestId("annotator-select")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("annotator-select"), { target: { value: "u-ann" } });
    expect(screen.getByTestId("assign-submit-btn")).toBeDisabled();
  });

  it("is enabled when both document and annotator are selected", async () => {
    renderForm();

    await waitFor(() => {
      expect(screen.getByTestId("document-select")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("document-select"), { target: { value: "doc-1" } });
    fireEvent.change(screen.getByTestId("annotator-select"), { target: { value: "u-ann" } });

    expect(screen.getByTestId("assign-submit-btn")).not.toBeDisabled();
  });
});

// ── Scenario 7: Successful task creation ──────────────────────────────────

describe("Scenario 7 — Successful task creation adds task to queue", () => {
  it("calls onAssign with the new task and shows toast on 201", async () => {
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

    await waitFor(() => {
      expect(screen.getByTestId("document-select")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("document-select"), { target: { value: "doc-1" } });
    fireEvent.change(screen.getByTestId("annotator-select"), { target: { value: "u-ann" } });
    fireEvent.click(screen.getByTestId("assign-submit-btn"));

    await waitFor(() => {
      expect(onAssign).toHaveBeenCalledWith(newTask);
    });
    expect(mockToast).toHaveBeenCalledWith("Task assigned successfully", "good");
  });
});

// ── Scenario 8: 409 shows inline error, form stays open ───────────────────

describe("Scenario 8 — 409 shows inline error and keeps form open", () => {
  it("shows inline error on 409 and does not call onAssign", async () => {
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

    await waitFor(() => {
      expect(screen.getByTestId("document-select")).toBeInTheDocument();
    });

    fireEvent.change(screen.getByTestId("document-select"), { target: { value: "doc-1" } });
    fireEvent.change(screen.getByTestId("annotator-select"), { target: { value: "u-ann" } });
    fireEvent.click(screen.getByTestId("assign-submit-btn"));

    await waitFor(() => {
      expect(screen.getByTestId("assign-form-error")).toBeInTheDocument();
    });

    expect(screen.getByTestId("assign-form-error")).toHaveTextContent("This document already has an active task.");
    expect(screen.getByTestId("assign-task-form")).toBeInTheDocument();
    expect(onAssign).not.toHaveBeenCalled();
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
    // No POST to annotation-tasks should have been made
    const postCall = mockAuthFetch.mock.calls.find(
      (args) => args[0] === "/api/v1/annotation-tasks",
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
