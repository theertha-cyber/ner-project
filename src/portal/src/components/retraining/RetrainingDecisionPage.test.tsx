import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "@/hooks/use-toast";
import { RetrainingDecisionPage } from "./RetrainingDecisionPage";
import type {
  PromotionEvidence,
  RetrainingDecision,
} from "@/types/human-gated-retraining";

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

const NOTE =
  "Spans created by production review since this model version was trained. This is not a " +
  "dataset readiness measure and is not comparable to the per-entity-type readiness threshold.";

const EMPTY_OVERVIEW = {
  manual: { count: 0, latest_at: null },
  automated: { count: 0, latest_at: null },
  import: { count: 0, latest_at: null },
};

function trained(overrides: Partial<RetrainingDecision> = {}): RetrainingDecision {
  return {
    kind: "accumulation_since_training",
    has_trained_model: true,
    serving_model_version: "3",
    spans_accumulated: 134,
    by_entity_type: { organization: 120, person_name: 14 },
    by_source: { manual: 104, automated: 30 },
    eligible_overview: EMPTY_OVERVIEW,
    training_run_in_flight: false,
    spans_from_base_model: 0,
    note: NOTE,
    ...overrides,
  } as RetrainingDecision;
}

function untrained(): RetrainingDecision {
  return {
    kind: "accumulation_since_training",
    has_trained_model: false,
    serving_model_version: null,
    state: "no_trained_model",
    state_detail:
      "This tenant has no trained model and is served by the base model. There is no trained " +
      "version for accumulation to be measured against.",
    training_run_in_flight: false,
    spans_from_base_model: 4,
    note: NOTE,
    eligible_overview: EMPTY_OVERVIEW,
  };
}

function evidence(overrides: Partial<PromotionEvidence> = {}): PromotionEvidence {
  return {
    candidate: {
      version_number: 4,
      status: "completed",
      metrics: { eval_f1: 0.91, eval_precision: 0.93, eval_recall: 0.89 },
      trained_on_span_count: 1200,
      training_job_id: "job-4",
      created_at: "2026-09-07T10:00:00Z",
    },
    current: {
      version_number: 3,
      status: "promoted",
      metrics: { eval_f1: 0.72, eval_precision: 0.7, eval_recall: 0.74 },
      trained_on_span_count: 300,
      training_job_id: "job-3",
      created_at: "2026-08-07T10:00:00Z",
    },
    comparable: false,
    note:
      "These two runs were trained on materially different dataset sizes (1200 and 300 " +
      "confirmed spans). Their metrics are not directly comparable.",
    ...overrides,
  };
}

function respondWith({
  decision = trained(),
  promotion = evidence(),
  retrainWarning = null,
}: {
  decision?: RetrainingDecision;
  promotion?: PromotionEvidence;
  retrainWarning?: string | null;
} = {}) {
  mockFetch.mockImplementation((url: string, init?: RequestInit) => {
    const target = String(url);
    if (target.includes("/retraining-decision")) {
      return Promise.resolve({ ok: true, json: async () => decision });
    }
    if (target.includes("/training-promotion-evidence")) {
      return Promise.resolve({ ok: true, json: async () => promotion });
    }
    if (target.includes("/training-retrain-requests")) {
      return Promise.resolve({
        ok: true,
        headers: { get: (name: string) => (name === "X-Retrain-Warning" ? retrainWarning : null) },
        json: async () => ({
          id: "job-new",
          status: "pending_approval",
          run_number: 5,
          run_name: "run-005-20260908",
        }),
      });
    }
    if (target.includes("/models/active")) {
      return Promise.resolve({ ok: true, json: async () => ({ model: null }) });
    }
    // `/api/v1/models`
    return Promise.resolve({
      ok: true,
      json: async () => ({
        items: [
          { version_number: 4, status: "completed" },
          { version_number: 3, status: "promoted" },
        ],
      }),
    });
  });
}

function renderPage() {
  render(<RetrainingDecisionPage />, { wrapper: createWrapper() });
}

beforeEach(() => {
  mockFetch.mockReset();
});

describe("the retraining decision surface", () => {
  it("shows the accumulation figure against the serving version", async () => {
    respondWith();
    renderPage();

    expect(await screen.findByText("134")).toBeInTheDocument();
    expect(
      screen.getByText(/confirmed spans from production review since version 3 was trained/),
    ).toBeInTheDocument();
    expect(screen.getByText("Model version 3")).toBeInTheDocument();
  });

  it("shows the eligible-and-waiting overview per source", async () => {
    respondWith({
      decision: trained({
        eligible_overview: {
          manual: { count: 2, latest_at: "2026-09-10T00:00:00Z" },
          automated: { count: 1, latest_at: "2026-09-10T00:00:00Z" },
          import: { count: 3, latest_at: null },
        },
      } as Partial<RetrainingDecision>),
    });
    renderPage();

    expect(await screen.findByText(/2 completed manual annotation tasks/)).toBeInTheDocument();
    expect(screen.getByText(/1 annotator-approved automated batch/)).toBeInTheDocument();
    expect(screen.getByText(/3 mapped import files/)).toBeInTheDocument();
  });

  it("breaks the figure down per entity type", async () => {
    respondWith();
    renderPage();

    expect(await screen.findByText("organization")).toBeInTheDocument();
    expect(screen.getByText("120")).toBeInTheDocument();
    expect(screen.getByText("person_name")).toBeInTheDocument();
    expect(screen.getByText("14")).toBeInTheDocument();
  });

  it("shows a tenant with no trained model distinctly, not as a zero", async () => {
    respondWith({ decision: untrained() });
    renderPage();

    expect(await screen.findByText("Base model")).toBeInTheDocument();
    expect(screen.getByText(/no trained model/i)).toBeInTheDocument();
    // The half that catches a screen rendering both: there is no figure to misread as
    // "nothing to do".
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("says the figure is not a readiness measure", async () => {
    respondWith();
    renderPage();

    expect(await screen.findByText(/not a dataset readiness measure/)).toBeInTheDocument();
    expect(screen.getByText(/Nothing is started automatically/)).toBeInTheDocument();
  });

  it("says so when a run is already in flight", async () => {
    respondWith({
      decision: trained({
        training_run_in_flight: true,
        in_flight_detail:
          "A training job is pending approval, queued, or running. Spans are recorded as " +
          "consumed only when a run completes, so this figure still includes spans that run " +
          "may consume.",
      } as Partial<RetrainingDecision>),
    });
    renderPage();

    expect(
      await screen.findByText(/consumed only when a run completes/),
    ).toBeInTheDocument();
  });
});

describe("requesting a retrain", () => {
  it("asks rather than starts, and says so", async () => {
    respondWith();
    renderPage();

    const button = await screen.findByRole("button", { name: /request a retrain/i });
    expect(
      screen.getByText(/Nothing trains until it is approved/),
    ).toBeInTheDocument();

    fireEvent.click(button);

    await waitFor(() => {
      expect(
        mockFetch.mock.calls.some(([url]) =>
          String(url).includes("/training-retrain-requests"),
        ),
      ).toBe(true);
    });
    expect(await screen.findByText(/waiting for System Admin approval/)).toBeInTheDocument();
  });

  it("surfaces the zero-accumulation warning without refusing", async () => {
    respondWith({
      decision: trained({ spans_accumulated: 0, by_entity_type: {} } as Partial<RetrainingDecision>),
      retrainWarning: "no-accumulated-spans",
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: /request a retrain/i }));

    expect(
      await screen.findByText(/no new reviewed evidence has accumulated/i),
    ).toBeInTheDocument();
  });
});

describe("the promotion decision surface", () => {
  it("shows both versions' metrics with what each was trained on", async () => {
    respondWith();
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Version 4" }));

    expect(await screen.findByText("Candidate")).toBeInTheDocument();
    expect(screen.getByText("Currently serving")).toBeInTheDocument();
    expect(screen.getByText("0.910")).toBeInTheDocument();
    expect(screen.getByText("0.720")).toBeInTheDocument();
    expect(screen.getByText("1200 spans")).toBeInTheDocument();
    expect(screen.getByText("300 spans")).toBeInTheDocument();
  });

  it("flags materially different dataset sizes", async () => {
    respondWith();
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Version 4" }));

    expect(
      await screen.findByText(/materially different dataset sizes/),
    ).toBeInTheDocument();
    expect(screen.getByText(/not directly comparable/)).toBeInTheDocument();
  });

  it("offers no verdict and no promote control, even with a better candidate", async () => {
    respondWith();
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Version 4" }));
    await screen.findByText("Candidate");

    // The candidate's metrics beat the serving version's on every axis and the screen still
    // says nothing about which is better. A surface that judged only when the winner was
    // obvious would pass a test over two similar versions and fail a real decision.
    for (const word of [/better/i, /worse/i, /recommend/i, /should promote/i]) {
      expect(screen.queryByText(word)).not.toBeInTheDocument();
    }
    // Promotion stays on the models screen. This page reads.
    expect(screen.queryByRole("button", { name: /^promote/i })).not.toBeInTheDocument();
    expect(screen.getByText(/Promoting is done from the models screen/)).toBeInTheDocument();
  });

  it("says when there is no promoted version to compare against", async () => {
    respondWith({
      promotion: evidence({
        current: null,
        comparable: null,
        note:
          "There is no other promoted model version to compare against. The candidate's " +
          "metrics are reported on their own.",
      }),
    });
    renderPage();

    fireEvent.click(await screen.findByRole("button", { name: "Version 4" }));

    expect(
      await screen.findByText(/No other promoted version to compare against/),
    ).toBeInTheDocument();
  });
});
