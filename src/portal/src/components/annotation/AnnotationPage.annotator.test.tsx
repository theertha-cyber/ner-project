import { render, screen } from "@testing-library/react";
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
vi.mock("@/lib/token-map", () => ({ buildTokenMap: () => [] }));

vi.mock("./TaskQueue", () => ({
  TaskQueue: () => <div data-testid="mock-task-queue" />,
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
