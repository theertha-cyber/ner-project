/**
 * The pre-submission readiness report inside the training submission panel (seed-bootstrap 6.3).
 *
 * Split from `submit-job-slideover.test.tsx`, which stubs this hook out so its own
 * `mockResolvedValueOnce` sequencing stays deterministic. Here the hook is the thing under test.
 *
 * The load-bearing assertion is the last one. Naming shortfalls is useful; leaving the submit
 * button enabled while naming them is the requirement — a readiness check that disabled
 * submission would duplicate `NER_MIN_ENTITIES_PER_TYPE` and take a decision away from the
 * System Admin approval step (ADR-009, ADR-010, verification.md Risk 6).
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SubmitJobSlideover } from "./submit-job-slideover";
import type { TrainingReadiness } from "@/types/seed-bootstrap";

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

let readiness: TrainingReadiness | undefined;
let readinessLoading = false;

vi.mock("@/hooks/use-training-readiness", () => ({
  useTrainingReadiness: () => ({ data: readiness, isLoading: readinessLoading }),
}));

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={qc}>{children}</QueryClientProvider>;
  };
}

describe("SubmitJobSlideover — readiness report", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue(new Response("span1\nspan2\n", { status: 200 }));
    readinessLoading = false;
    readiness = undefined;
  });

  it("names every shortfalling entity type with its count", async () => {
    readiness = {
      threshold_per_entity_type: 200,
      entity_types: [
        { entity_type: "institute", count: 250, threshold: 200, meets_threshold: true, shortfall: 0 },
        { entity_type: "person_name", count: 40, threshold: 200, meets_threshold: false, shortfall: 160 },
        { entity_type: "skill", count: 0, threshold: 200, meets_threshold: false, shortfall: 200 },
      ],
      shortfalling_entity_types: [
        { entity_type: "person_name", count: 40 },
        { entity_type: "skill", count: 0 },
      ],
      ready: false,
      advisory: true,
      blocks_submission: false,
    };

    render(<SubmitJobSlideover open={true} onClose={vi.fn()} sourceScope="automated" />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("person_name")).toBeDefined();
    });
    expect(screen.getByText("40 / 200")).toBeDefined();
    // A configured type nobody has annotated is named too, at zero — the case an enumeration of
    // existing spans alone would silently omit.
    expect(screen.getByText("skill")).toBeDefined();
    expect(screen.getByText("0 / 200")).toBeDefined();
    // The type that is fine is not listed as a shortfall.
    expect(screen.queryByText("institute")).toBeNull();
  });

  it("leaves submission enabled while reporting shortfalls", async () => {
    readiness = {
      threshold_per_entity_type: 200,
      entity_types: [
        { entity_type: "person_name", count: 3, threshold: 200, meets_threshold: false, shortfall: 197 },
      ],
      shortfalling_entity_types: [{ entity_type: "person_name", count: 3 }],
      ready: false,
      advisory: true,
      blocks_submission: false,
    };

    render(<SubmitJobSlideover open={true} onClose={vi.fn()} sourceScope="automated" />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("person_name")).toBeDefined();
    });
    expect(screen.getByRole("button", { name: /submit training job/i })).not.toBeDisabled();
    expect(screen.getByText(/system admin decides/i)).toBeDefined();
  });

  it("says so when every type meets the threshold", async () => {
    readiness = {
      threshold_per_entity_type: 200,
      entity_types: [
        { entity_type: "institute", count: 250, threshold: 200, meets_threshold: true, shortfall: 0 },
      ],
      shortfalling_entity_types: [],
      ready: true,
      advisory: true,
      blocks_submission: false,
    };

    render(<SubmitJobSlideover open={true} onClose={vi.fn()} sourceScope="automated" />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/every entity type meets the threshold/i)).toBeDefined();
    });
  });

  it("keeps submission enabled when the readiness report cannot be loaded", async () => {
    readiness = undefined;

    render(<SubmitJobSlideover open={true} onClose={vi.fn()} sourceScope="automated" />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/unable to check per-type readiness/i)).toBeDefined();
    });
    expect(screen.getByRole("button", { name: /submit training job/i })).not.toBeDisabled();
  });
});
