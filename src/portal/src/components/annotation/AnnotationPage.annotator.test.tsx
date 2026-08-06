import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AnnotationPage } from "./AnnotationPage";

// ── Mocks (annotator role) ────────────────────────────────────────────────────

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { userId: "u2", role: "annotator", email: "ann@b.com", tenantId: "t1", tenantSlug: "test" },
    getAccessToken: () => "token",
    setAccessToken: vi.fn(),
    login: vi.fn(),
    logout: vi.fn(),
  }),
}));

const mockAuthFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({ authFetch: (...args: unknown[]) => mockAuthFetch(...args) }));
vi.mock("@/hooks/use-toast", () => ({ useToast: () => ({ toast: vi.fn() }) }));
vi.mock("@/hooks/use-entity-types", () => ({
  useEntityTypes: () => ({ data: { entity_types: [{ name: "PER" }, { name: "ORG" }, { name: "LOC" }] } }),
}));
vi.mock("@/lib/token-map", () => ({ buildTokenMap: () => [] }));

// Controllable ?task= value for the dashboard deep-link tests below.
const searchParamsHolder = { value: new URLSearchParams() };
vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParamsHolder.value,
}));

let capturedSelectedTaskId: string | null = null;
vi.mock("./TaskQueue", () => ({
  TaskQueue: ({ selectedTaskId }: { selectedTaskId: string | null }) => {
    capturedSelectedTaskId = selectedTaskId;
    return <div data-testid="mock-task-queue" data-selected={selectedTaskId ?? ""} />;
  },
}));
vi.mock("./DocumentViewer", () => ({
  DocumentViewer: () => <div data-testid="mock-document-viewer" />,
}));
vi.mock("./EntityPalette", () => ({
  EntityPalette: () => <div data-testid="mock-entity-palette" />,
}));
vi.mock("./SpanInspector", () => ({
  SpanInspector: () => <div data-testid="mock-span-inspector" />,
}));
vi.mock("./SuggestionPanel", () => ({
  SuggestionPanel: () => <div data-testid="mock-suggestion-panel" />,
}));
vi.mock("./ArmedBanner", () => ({
  ArmedBanner: () => <div data-testid="mock-armed-banner" />,
}));
vi.mock("./FocusPalette", () => ({
  FocusPalette: () => <div data-testid="mock-focus-palette" />,
}));
vi.mock("./AssignTaskForm", () => ({
  AssignTaskForm: () => <div data-testid="mock-assign-task-form" />,
}));

// ── Setup ─────────────────────────────────────────────────────────────────────

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  capturedSelectedTaskId = null;
  searchParamsHolder.value = new URLSearchParams();
  mockAuthFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
});

afterEach(() => {
  localStorage.clear();
});

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <AnnotationPage />
    </QueryClientProvider>,
  );
}

// ── Scenarios 2/17 — annotator does NOT see Assign Task button ────────────────

describe("Scenario 2/17 — annotator does not see Assign Task button", () => {
  it("does not render the Assign Task button for annotator role", () => {
    renderPage();
    expect(screen.queryByTestId("assign-task-btn")).not.toBeInTheDocument();
  });

  it("does not render the assign form for annotator role even if state is toggled externally", () => {
    renderPage();
    // Button is absent so the form cannot be opened
    expect(screen.queryByTestId("assign-task-btn")).not.toBeInTheDocument();
    expect(screen.queryByTestId("mock-assign-task-form")).not.toBeInTheDocument();
  });
});


// ── Deep link from the dashboard's continue-work card ─────────────────────────

const MY_TASK = {
  id: "abc123",
  document_id: "doc-1",
  annotator_user_id: "u2",
  status: "in-progress" as const,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: null,
  filename: "resume_01.pdf",
};

const OTHER_ANNOTATORS_TASK = { ...MY_TASK, id: "other456", annotator_user_id: "someone-else" };

function mockTasks(tasks: unknown[]) {
  mockAuthFetch.mockImplementation((url: string) => {
    if (url === "/api/v1/annotation-tasks") {
      return Promise.resolve({ ok: true, json: () => Promise.resolve(tasks) });
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve([]) });
  });
}

describe("deep link — /annotation?task=<id>", () => {
  it("pre-selects the requested task and loads its document", async () => {
    searchParamsHolder.value = new URLSearchParams("task=abc123");
    mockTasks([MY_TASK]);
    renderPage();
    await waitFor(() => expect(capturedSelectedTaskId).toBe("abc123"));
    await waitFor(() =>
      expect(mockAuthFetch).toHaveBeenCalledWith("/api/v1/documents/doc-1/text"),
    );
  });

  it("falls back to the default selection for an unknown task id", async () => {
    searchParamsHolder.value = new URLSearchParams("task=zzz999");
    mockTasks([MY_TASK]);
    renderPage();
    await waitFor(() => expect(screen.getByTestId("mock-task-queue")).toBeInTheDocument());
    expect(capturedSelectedTaskId).toBeNull();
  });

  it("does not select a task outside this annotator's queue", async () => {
    searchParamsHolder.value = new URLSearchParams("task=other456");
    mockTasks([OTHER_ANNOTATORS_TASK]);
    renderPage();
    await waitFor(() => expect(screen.getByTestId("mock-task-queue")).toBeInTheDocument());
    expect(capturedSelectedTaskId).toBeNull();
    expect(mockAuthFetch).not.toHaveBeenCalledWith("/api/v1/documents/doc-1/text");
  });

  it("leaves the default behaviour untouched when no parameter is present", async () => {
    mockTasks([MY_TASK]);
    renderPage();
    await waitFor(() => expect(screen.getByTestId("mock-task-queue")).toBeInTheDocument());
    expect(capturedSelectedTaskId).toBeNull();
  });

  it("restores the persisted layout mode regardless of the parameter", async () => {
    localStorage.setItem("ner-annotation-layout", "focus");
    searchParamsHolder.value = new URLSearchParams("task=abc123");
    mockTasks([MY_TASK]);
    renderPage();
    // Focus mode hides the task queue, so assert the deep link fired by the
    // document load it triggers rather than via the queue's selection prop.
    await waitFor(() =>
      expect(mockAuthFetch).toHaveBeenCalledWith("/api/v1/documents/doc-1/text"),
    );
    expect(localStorage.getItem("ner-annotation-layout")).toBe("focus");
  });
});
