import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AnnotationPage } from "./AnnotationPage";
import type { AnnotationTask } from "./TaskQueue";

// ── Mocks ──────────────────────────────────────────────────────────────────

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    user: { userId: "u1", role: "tenant_admin", email: "a@b.com", tenantId: "t1", tenantSlug: "test" },
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

vi.mock("./TaskQueue", () => ({
  TaskQueue: ({
    tasks,
    onSelect,
  }: {
    tasks: AnnotationTask[];
    onSelect: (task: AnnotationTask) => void;
  }) => (
    <div data-testid="mock-task-queue">
      {tasks.map((t) => (
        <div
          key={t.id}
          data-testid={`task-row-${t.id}`}
          onClick={() => onSelect(t)}
        />
      ))}
    </div>
  ),
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
  SuggestionPanel: ({
    suggestions,
    onPromote,
  }: {
    suggestions: Array<{ id: string }>;
    onPromote: (suggestId: string) => void;
  }) => (
    <div data-testid="mock-suggestion-panel">
      {suggestions.map((s) => (
        <button key={s.id} data-testid={`mock-promote-${s.id}`} onClick={() => onPromote(s.id)} />
      ))}
    </div>
  ),
}));

vi.mock("./ArmedBanner", () => ({
  ArmedBanner: ({ onDisarm }: { onDisarm: () => void }) => (
    <div data-testid="mock-armed-banner">
      <button data-testid="banner-disarm" onClick={onDisarm}>esc · done</button>
    </div>
  ),
}));

vi.mock("./FocusPalette", () => ({
  FocusPalette: () => <div data-testid="mock-focus-palette" />,
}));

vi.mock("./AssignTaskForm", () => ({
  AssignTaskForm: ({ onCancel }: { onCancel: () => void }) => (
    <div data-testid="mock-assign-task-form">
      <button data-testid="mock-cancel-btn" onClick={onCancel}>Cancel</button>
    </div>
  ),
}));

// ── Fixtures ──────────────────────────────────────────────────────────────────

const mockTask: AnnotationTask = {
  id: "task-1",
  document_id: "doc-1",
  annotator_user_id: "u1",
  status: "in-progress",
  created_at: "2026-01-01",
  updated_at: null,
  filename: "invoice-2026-00417.pdf",
  document_status: "processed",
  span_count: 3,
};

const mockSuggestedSpan = {
  id: "s-1",
  entity_type: "vendor_name",
  char_start: 0,
  char_end: 4,
  text: "Acme",
  confidence: 0.85,
};

// ── Helpers ─────────────────────────────────────────────────────────────────

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function renderPage() {
  const client = makeQueryClient();
  return render(
    <QueryClientProvider client={client}>
      <AnnotationPage />
    </QueryClientProvider>,
  );
}

// ── Setup ────────────────────────────────────────────────────────────────────

const mockRequestFullscreen = vi.fn().mockResolvedValue(undefined);

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  mockAuthFetch.mockResolvedValue({ ok: true, json: () => Promise.resolve([]) });
  Object.defineProperty(document.documentElement, "requestFullscreen", {
    value: mockRequestFullscreen,
    writable: true,
    configurable: true,
  });
});

afterEach(() => {
  localStorage.clear();
});

// ── Scenario 1: Default 3-pane layout on first mount ─────────────────────────

describe("Scenario 1 — Default layout renders three columns", () => {
  it("renders task queue, document viewer, entity panel and 3-pane button active", async () => {
    renderPage();

    expect(screen.getByTestId("task-queue-column")).toBeInTheDocument();
    expect(screen.getByTestId("document-viewer-column")).toBeInTheDocument();
    expect(screen.getByTestId("entity-panel-column")).toBeInTheDocument();
    expect(screen.getByTestId("layout-btn-3pane")).toBeInTheDocument();
    expect(screen.getByTestId("layout-btn-focus")).toBeInTheDocument();
  });
});

// ── Scenario 2 & 3: Clicking Focus does not call requestFullscreen ────────────

describe("Scenario 2 & 3 — Clicking Focus does not call requestFullscreen", () => {
  it("clicking Focus hides task queue, shows Focus as active, does not call requestFullscreen", async () => {
    renderPage();

    expect(screen.getByTestId("task-queue-column")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("layout-btn-focus"));

    expect(screen.queryByTestId("task-queue-column")).not.toBeInTheDocument();
    expect(mockRequestFullscreen).not.toHaveBeenCalled();
    expect(screen.getByTestId("mock-focus-palette")).toBeInTheDocument();
  });

  it("clicking 3-pane after Focus restores three-column layout", async () => {
    renderPage();

    fireEvent.click(screen.getByTestId("layout-btn-focus"));
    expect(screen.queryByTestId("task-queue-column")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("layout-btn-3pane"));
    expect(screen.getByTestId("task-queue-column")).toBeInTheDocument();
    expect(screen.queryByTestId("mock-focus-palette")).not.toBeInTheDocument();
  });
});

// ── Scenario 4: Layout preference restored from localStorage ─────────────────

describe("Scenario 4 — localStorage focus preference restored on mount", () => {
  it("renders in focus mode when localStorage has focus preference", () => {
    localStorage.setItem("ner-annotation-layout", "focus");
    renderPage();

    expect(screen.queryByTestId("task-queue-column")).not.toBeInTheDocument();
    expect(screen.getByTestId("mock-focus-palette")).toBeInTheDocument();
  });
});

// ── Scenario 21: SpanInspector renders inside right entity panel (3-pane) ─────

describe("Scenario 21 — SpanInspector renders in right entity panel, not center column", () => {
  it("center document column does NOT contain span-inspector", async () => {
    renderPage();
    // SpanInspector only appears when a span is selected; by default it's absent
    // The key structural guarantee: span-inspector is never rendered inside
    // document-viewer-column regardless of state
    const docColumn = screen.getByTestId("document-viewer-column");
    expect(within(docColumn).queryByTestId("mock-span-inspector")).not.toBeInTheDocument();
  });

  it("entity panel column contains the entity palette (structure baseline)", () => {
    renderPage();
    const entityPanel = screen.getByTestId("entity-panel-column");
    expect(within(entityPanel).getByTestId("mock-entity-palette")).toBeInTheDocument();
  });
});

// ── Scenario 25: SuggestionPanel renders inside right entity panel (3-pane) ───

describe("Scenario 25 — SuggestionPanel renders in right entity panel, not center column", () => {
  it("suggestion panel appears in entity-panel-column after task selection with suggestions", async () => {
    mockAuthFetch
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([mockTask]),
      })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ text: "hello world" }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve([]) })
      .mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve([mockSuggestedSpan]),
      });

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId("task-row-task-1")).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId("task-row-task-1"));

    await waitFor(() => {
      expect(screen.getByTestId("mock-suggestion-panel")).toBeInTheDocument();
    });

    // SuggestionPanel must be in entity panel, NOT in document viewer column
    const entityPanel = screen.getByTestId("entity-panel-column");
    const docColumn = screen.getByTestId("document-viewer-column");

    expect(within(entityPanel).getByTestId("mock-suggestion-panel")).toBeInTheDocument();
    expect(within(docColumn).queryByTestId("mock-suggestion-panel")).not.toBeInTheDocument();
  });

  it("center document column does NOT contain suggestion cards", async () => {
    renderPage();
    const docColumn = screen.getByTestId("document-viewer-column");
    expect(within(docColumn).queryByTestId("mock-suggestion-panel")).not.toBeInTheDocument();
  });
});

// ── Annotator filter ──────────────────────────────────────────────────────────

describe("Scenario 8 — Annotator sees only their assigned tasks", () => {
  it("renders task queue component", () => {
    renderPage();
    expect(screen.getByTestId("mock-task-queue")).toBeInTheDocument();
  });
});

// ── Scenarios 1/16 — tenant_admin sees Assign Task button ────────────────────

describe("Scenario 1/16 — tenant_admin sees Assign Task button", () => {
  it("renders the Assign Task button when user is tenant_admin", () => {
    renderPage();
    expect(screen.getByTestId("assign-task-btn")).toBeInTheDocument();
  });
});

// ── Scenario 3 — Clicking Assign Task opens inline form ──────────────────────

describe("Scenario 3 — Clicking Assign Task button expands the inline form", () => {
  it("shows the assign form when button is clicked", () => {
    renderPage();
    fireEvent.click(screen.getByTestId("assign-task-btn"));
    expect(screen.getByTestId("mock-assign-task-form")).toBeInTheDocument();
  });

  it("hides the form when Cancel is clicked inside the form", () => {
    renderPage();
    fireEvent.click(screen.getByTestId("assign-task-btn"));
    expect(screen.getByTestId("mock-assign-task-form")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("mock-cancel-btn"));
    expect(screen.queryByTestId("mock-assign-task-form")).not.toBeInTheDocument();
  });
});

// ── Task lifecycle: promotion happens once, on task open ──────────────────────

const mockUnannotatedTask: AnnotationTask = {
  ...mockTask,
  id: "task-unannotated",
  status: "unannotated",
};

const mockCompletedTask: AnnotationTask = {
  ...mockTask,
  id: "task-completed",
  status: "completed",
};

function queueAuthFetchTasksList(tasks: AnnotationTask[]) {
  mockAuthFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve(tasks) });
}

function queueAuthFetchDocLoad() {
  mockAuthFetch
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ text: "hello world" }) })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve([]) })
    .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve([]) });
}

describe("Scenario 4 — Opening an unannotated task promotes it to in-progress", () => {
  it("sends a PATCH with in-progress status on selection", async () => {
    queueAuthFetchTasksList([mockUnannotatedTask]);
    mockAuthFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ id: mockUnannotatedTask.id, status: "in-progress" }) });
    queueAuthFetchDocLoad();

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId(`task-row-${mockUnannotatedTask.id}`)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId(`task-row-${mockUnannotatedTask.id}`));

    await waitFor(() => {
      expect(mockAuthFetch).toHaveBeenCalledWith(
        `/api/v1/annotation-tasks/${mockUnannotatedTask.id}`,
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ status: "in-progress" }),
        }),
      );
    });
  });
});

describe("Scenario 5 — In-progress transition fires only once per session", () => {
  it("sends exactly one in-progress PATCH across select, switch, and re-select", async () => {
    queueAuthFetchTasksList([mockUnannotatedTask, mockTask]);
    mockAuthFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ id: mockUnannotatedTask.id, status: "in-progress" }) });
    queueAuthFetchDocLoad();
    queueAuthFetchDocLoad();
    queueAuthFetchDocLoad();

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId(`task-row-${mockUnannotatedTask.id}`)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId(`task-row-${mockUnannotatedTask.id}`));
    await waitFor(() => {
      expect(mockAuthFetch).toHaveBeenCalledWith(
        `/api/v1/annotation-tasks/${mockUnannotatedTask.id}`,
        expect.objectContaining({ method: "PATCH" }),
      );
    });

    fireEvent.click(screen.getByTestId(`task-row-${mockTask.id}`));
    await waitFor(() => screen.getByTestId("mock-document-viewer"));

    fireEvent.click(screen.getByTestId(`task-row-${mockUnannotatedTask.id}`));
    await waitFor(() => screen.getByTestId("mock-document-viewer"));

    const patchCalls = mockAuthFetch.mock.calls.filter(
      (call) => call[1]?.method === "PATCH" && call[0] === `/api/v1/annotation-tasks/${mockUnannotatedTask.id}`,
    );
    expect(patchCalls).toHaveLength(1);
  });
});

describe("Scenario 6 — Opening a completed task sends no status request", () => {
  it("sends no PATCH and renders the document for a completed task", async () => {
    queueAuthFetchTasksList([mockCompletedTask]);
    queueAuthFetchDocLoad();

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId(`task-row-${mockCompletedTask.id}`)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId(`task-row-${mockCompletedTask.id}`));

    await waitFor(() => {
      expect(screen.getByTestId("mock-document-viewer")).toBeInTheDocument();
    });

    const patchCalls = mockAuthFetch.mock.calls.filter((call) => call[1]?.method === "PATCH");
    expect(patchCalls).toHaveLength(0);
  });
});

describe("Scenario 7 — Creating a span does not send a status request", () => {
  it("promoting a suggestion sends the span request but no status PATCH", async () => {
    queueAuthFetchTasksList([mockTask]);
    mockAuthFetch
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ text: "hello world" }) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve([]) })
      .mockResolvedValueOnce({ ok: true, json: () => Promise.resolve([mockSuggestedSpan]) });
    mockAuthFetch.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve({
        id: "confirmed-1",
        entity_type: mockSuggestedSpan.entity_type,
        char_start: mockSuggestedSpan.char_start,
        char_end: mockSuggestedSpan.char_end,
        text: mockSuggestedSpan.text,
        confidence: 1.0,
      }),
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId(`task-row-${mockTask.id}`)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId(`task-row-${mockTask.id}`));

    await waitFor(() => {
      expect(screen.getByTestId(`mock-promote-${mockSuggestedSpan.id}`)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByTestId(`mock-promote-${mockSuggestedSpan.id}`));

    await waitFor(() => {
      expect(mockAuthFetch).toHaveBeenCalledWith(
        `/api/v1/documents/${mockTask.document_id}/spans/promote/${mockSuggestedSpan.id}`,
        expect.objectContaining({ method: "POST" }),
      );
    });

    const patchCalls = mockAuthFetch.mock.calls.filter((call) => call[1]?.method === "PATCH");
    expect(patchCalls).toHaveLength(0);
  });
});

// ── Action bar: completion flow ───────────────────────────────────────────────

describe("Scenario 9 — Mark as Completed completes the task", () => {
  it("sends a PATCH with completed status and shows the completed badge on success", async () => {
    queueAuthFetchTasksList([mockTask]);
    queueAuthFetchDocLoad();
    mockAuthFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ id: mockTask.id, status: "completed" }) });

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId(`task-row-${mockTask.id}`)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId(`task-row-${mockTask.id}`));
    await waitFor(() => screen.getByTestId("mock-document-viewer"));

    fireEvent.click(screen.getByTestId("mark-completed-btn"));

    await waitFor(() => {
      expect(mockAuthFetch).toHaveBeenCalledWith(
        `/api/v1/annotation-tasks/${mockTask.id}`,
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ status: "completed" }),
        }),
      );
    });

    await waitFor(() => {
      expect(screen.getByTestId("status-badge")).toHaveTextContent("completed");
    });
  });
});

describe("Scenario 10 — Completing with no spans surfaces the error and keeps the task in-progress", () => {
  it("keeps the badge in_progress and re-enables the button on 422", async () => {
    queueAuthFetchTasksList([mockTask]);
    queueAuthFetchDocLoad();
    mockAuthFetch.mockResolvedValueOnce({
      ok: false,
      json: () => Promise.resolve({ detail: { message: "Document must have at least one confirmed span before task can be completed" } }),
    });

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId(`task-row-${mockTask.id}`)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId(`task-row-${mockTask.id}`));
    await waitFor(() => screen.getByTestId("mock-document-viewer"));

    const btn = screen.getByTestId("mark-completed-btn");
    fireEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByTestId("status-badge")).toHaveTextContent("in_progress");
    });
    await waitFor(() => {
      expect(screen.getByTestId("mark-completed-btn")).not.toBeDisabled();
    });
  });
});

describe("Scenario 11 — Re-completing an already completed task saves further edits", () => {
  it("sends a completed PATCH that succeeds with no transition error", async () => {
    queueAuthFetchTasksList([mockCompletedTask]);
    queueAuthFetchDocLoad();
    mockAuthFetch.mockResolvedValueOnce({ ok: true, json: () => Promise.resolve({ id: mockCompletedTask.id, status: "completed" }) });

    renderPage();

    await waitFor(() => {
      expect(screen.getByTestId(`task-row-${mockCompletedTask.id}`)).toBeInTheDocument();
    });
    fireEvent.click(screen.getByTestId(`task-row-${mockCompletedTask.id}`));
    await waitFor(() => screen.getByTestId("mock-document-viewer"));

    fireEvent.click(screen.getByTestId("mark-completed-btn"));

    await waitFor(() => {
      expect(mockAuthFetch).toHaveBeenCalledWith(
        `/api/v1/annotation-tasks/${mockCompletedTask.id}`,
        expect.objectContaining({
          method: "PATCH",
          body: JSON.stringify({ status: "completed" }),
        }),
      );
    });
    expect(screen.getByTestId("status-badge")).toHaveTextContent("completed");
  });
});
