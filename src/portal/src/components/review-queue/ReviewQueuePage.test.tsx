import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "@/hooks/use-toast";
import { ReviewQueuePage } from "./ReviewQueuePage";
import type { AccumulationReport, QueuedPrediction } from "@/types/confidence-review";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { tenantSlug: "acme-corp" } }),
}));

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <ToastProvider>{children}</ToastProvider>
      </QueryClientProvider>
    );
  };
}

// "Jane Roe works as a Data Analyst at Acme Corp in Chennai today." — `Acme Corp` at 36-45,
// the same document and offsets the backend tests use, so a mismatch between the two surfaces
// shows up as a disagreement about a case both describe.
const CONTEXT = "Jane Roe works as a Data Analyst at Acme Corp in Chennai today.";

function prediction(overrides: Partial<QueuedPrediction> = {}): QueuedPrediction {
  return {
    id: "pred-1",
    document_id: "doc-1",
    filename: "resume.pdf",
    entity_type: "organization",
    value: "Acme Corp",
    confidence: 0.62,
    char_start: 36,
    char_end: 45,
    model_version: "3",
    served_by_base_model: false,
    below_business_threshold: false,
    created_at: "2026-09-07T10:00:00Z",
    context: CONTEXT,
    context_char_start: 0,
    text_at_offsets: "Acme Corp",
    ...overrides,
  };
}

function accumulation(overrides: Partial<AccumulationReport> = {}): AccumulationReport {
  return {
    kind: "accumulation_since_training",
    model_version: "3",
    spans_accumulated: 40,
    spans_from_base_model: 0,
    note:
      "Spans created by production review since this model version was trained. This is not a " +
      "dataset readiness measure and is not comparable to the per-entity-type readiness threshold.",
    ...overrides,
  };
}

function respondWith({
  queue = [prediction()],
  total = queue.length,
  report = accumulation(),
}: {
  queue?: QueuedPrediction[];
  total?: number;
  report?: AccumulationReport;
} = {}) {
  mockFetch.mockImplementation((url: string, init?: RequestInit) => {
    if (String(url).includes("/review-accumulation")) {
      return Promise.resolve({ ok: true, json: async () => report });
    }
    if (String(url).includes("/resolve")) {
      const body = JSON.parse(String(init?.body ?? "{}"));
      return Promise.resolve({
        ok: true,
        json: async () => ({
          outcome_id: "out-1",
          outcome: body.outcome,
          route: "human",
          origin: "queue",
          entity_type: body.entity_type ?? "organization",
          char_start: body.char_start ?? 36,
          char_end: body.char_end ?? 45,
          span_id: body.outcome === "rejected" ? null : "span-1",
          rejected: body.outcome === "rejected",
        }),
      });
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({ items: queue, total, limit: 25, offset: 0 }),
    });
  });
}

beforeEach(() => {
  mockFetch.mockReset();
});

describe("ReviewQueuePage", () => {
  it("lists a queued prediction with its type, offsets, confidence and document", async () => {
    respondWith();
    render(<ReviewQueuePage />, { wrapper: createWrapper() });

    expect(await screen.findByText("organization")).toBeInTheDocument();
    expect(screen.getByText(/62%/)).toBeInTheDocument();
    expect(screen.getByText(/characters 36–45/)).toBeInTheDocument();
    expect(screen.getByText(/resume\.pdf/)).toBeInTheDocument();
  });

  it("marks the predicted span inside its sentence", async () => {
    respondWith();
    const { container } = render(<ReviewQueuePage />, { wrapper: createWrapper() });

    await screen.findByText("organization");
    const mark = container.querySelector("mark");
    // Highlighted from offsets, not by searching the excerpt for the value: the same text can
    // occur twice in a sentence and the first occurrence is not necessarily this mention.
    expect(mark?.textContent).toBe("Acme Corp");
  });

  it("confirms a prediction without sending a route", async () => {
    respondWith();
    render(<ReviewQueuePage />, { wrapper: createWrapper() });

    fireEvent.click(await screen.findByRole("button", { name: "Confirm" }));

    await waitFor(() => {
      const call = mockFetch.mock.calls.find((c) => String(c[0]).includes("/resolve"));
      expect(call).toBeTruthy();
      const body = JSON.parse(String(call![1].body));
      expect(body.outcome).toBe("confirmed");
      // The server stamps the route. A client that sent one could record LLM-route outcomes
      // from the human surface and make the agreement comparison meaningless.
      expect(body).not.toHaveProperty("route");
    });
  });

  it("sends corrected offsets, not a corrected value", async () => {
    respondWith();
    render(<ReviewQueuePage />, { wrapper: createWrapper() });

    fireEvent.click(await screen.findByRole("button", { name: "Correct" }));
    fireEvent.change(screen.getByLabelText(/End/), { target: { value: "50" } });
    fireEvent.click(screen.getByRole("button", { name: "Save correction" }));

    await waitFor(() => {
      const call = mockFetch.mock.calls.find((c) => String(c[0]).includes("/resolve"));
      const body = JSON.parse(String(call![1].body));
      expect(body.outcome).toBe("corrected");
      expect(body.char_start).toBe(36);
      expect(body.char_end).toBe(50);
      // A training span is defined by offsets over the document. A corrected *value* is a
      // different thing and belongs to the extraction review flow, which this does not touch.
      expect(body).not.toHaveProperty("corrected_value");
      expect(body).not.toHaveProperty("value");
    });
  });

  it("rejects a prediction as not an entity", async () => {
    respondWith();
    render(<ReviewQueuePage />, { wrapper: createWrapper() });

    fireEvent.click(await screen.findByRole("button", { name: "Not an entity" }));

    await waitFor(() => {
      const call = mockFetch.mock.calls.find((c) => String(c[0]).includes("/resolve"));
      expect(JSON.parse(String(call![1].body)).outcome).toBe("rejected");
    });
    expect(await screen.findByText(/no span created/i)).toBeInTheDocument();
  });

  it("flags a prediction whose document text has drifted from the extracted value", async () => {
    respondWith({
      queue: [prediction({ value: "Acme Corp", text_at_offsets: "Acme Corp." })],
    });
    render(<ReviewQueuePage />, { wrapper: createWrapper() });

    expect(await screen.findByText(/Check the offsets before confirming/)).toBeInTheDocument();
  });

  it("says when a prediction is not in extraction results", async () => {
    respondWith({ queue: [prediction({ below_business_threshold: true })] });
    render(<ReviewQueuePage />, { wrapper: createWrapper() });

    expect(await screen.findByText("Not in extraction results")).toBeInTheDocument();
  });

  it("shows an empty state rather than an empty list", async () => {
    respondWith({ queue: [], total: 0 });
    render(<ReviewQueuePage />, { wrapper: createWrapper() });

    expect(await screen.findByText(/Nothing waiting for review/)).toBeInTheDocument();
  });
});

describe("the accumulation figure", () => {
  it("reports the figure against the serving model version", async () => {
    respondWith();
    render(<ReviewQueuePage />, { wrapper: createWrapper() });

    expect(await screen.findByText("40")).toBeInTheDocument();
    expect(screen.getByText("Model version 3")).toBeInTheDocument();
    expect(screen.getByText(/since version 3 was trained/)).toBeInTheDocument();
  });

  it("is presented distinctly from dataset readiness", async () => {
    respondWith();
    render(<ReviewQueuePage />, { wrapper: createWrapper() });

    // ADR-010: readiness is a different quantity with its own threshold. The card says so
    // rather than leaving a bare number next to a progress bar to be read as one.
    expect(
      await screen.findByText(/not a dataset readiness measure/i),
    ).toBeInTheDocument();
    expect(screen.getByText(/Nothing is started automatically/i)).toBeInTheDocument();
  });

  it("does not present a base-model figure as a version delta", async () => {
    respondWith({
      report: accumulation({
        model_version: null,
        spans_accumulated: 0,
        spans_from_base_model: 25,
      }),
    });
    render(<ReviewQueuePage />, { wrapper: createWrapper() });

    expect(await screen.findByText("Base model")).toBeInTheDocument();
    expect(screen.getByText(/no version for this figure to be measured against/)).toBeInTheDocument();
    expect(screen.getByText(/25 reviewed/)).toBeInTheDocument();
  });

  it("keeps base-model spans out of the tenant figure", async () => {
    respondWith({
      report: accumulation({ spans_accumulated: 40, spans_from_base_model: 25 }),
    });
    render(<ReviewQueuePage />, { wrapper: createWrapper() });

    expect(await screen.findByText("40")).toBeInTheDocument();
    expect(
      screen.getByText(/A further 25 came from base-model predictions and are not counted here/),
    ).toBeInTheDocument();
  });
});
