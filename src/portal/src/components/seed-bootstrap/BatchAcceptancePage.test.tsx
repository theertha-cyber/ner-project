import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: vi.fn(() => ({ push: mockPush })),
}));

// A stable reference across re-renders, unlike a fresh `vi.fn()` per call — needed to assert
// on toast-call counts across a rerender (the "only toast once, on the transition" behavior).
const mockToast = vi.fn();
vi.mock("@/hooks/use-toast", () => ({
  useToast: vi.fn(() => ({ toast: mockToast })),
}));

vi.mock("@/hooks/use-documents", () => ({
  useDocuments: vi.fn(() => ({
    data: { documents: [{ id: "d1", filename: "a.pdf", purpose: "training" }], total: 1 },
    isLoading: false,
  })),
}));

vi.mock("@/hooks/use-entity-types", () => ({
  useEntityTypes: vi.fn(() => ({ data: { entity_types: [] } })),
}));

vi.mock("./BatchReviewDocument", () => ({ BatchReviewDocument: () => <div /> }));

const mockCreateBatch = { mutate: vi.fn(), isPending: false };
const mockUsePrelabelBatches = vi.fn();
const mockUsePrelabelBatch = vi.fn();
vi.mock("@/hooks/use-prelabel-batch", () => ({
  useCreatePrelabelBatch: vi.fn(() => mockCreateBatch),
  usePrelabelBatch: (...args: unknown[]) => mockUsePrelabelBatch(...args),
  usePrelabelBatches: (...args: unknown[]) => mockUsePrelabelBatches(...args),
}));

vi.mock("@/hooks/use-batch-acceptance", () => ({
  useAcceptBatch: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useBatchAcceptance: vi.fn(() => ({ data: undefined })),
  useStartAcceptanceReview: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useSubmitAcceptanceReview: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
}));

import { BatchAcceptancePage } from "./BatchAcceptancePage";

function batchesResult(batches: unknown[]) {
  return { data: { batches } };
}

function batchDetail(overrides: Record<string, unknown>) {
  return {
    data: {
      batch_id: "x",
      status: "completed",
      state: "completed",
      document_count: 5,
      succeeded: 5,
      failed: 0,
      ungrounded: 0,
      documents: [],
      annotator_review_status: null,
      ...overrides,
    },
  };
}

describe("BatchAcceptancePage — two-stage flow, both stages stay visible", () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockCreateBatch.mutate.mockClear();
    mockUsePrelabelBatch.mockReset();
    mockToast.mockClear();
  });

  it("shows the initial-batch picker (capped, no radio) and a locked stage 2 when no batch exists yet", () => {
    mockUsePrelabelBatches.mockReturnValue(batchesResult([]));
    mockUsePrelabelBatch.mockReturnValue({ data: undefined });

    render(<BatchAcceptancePage />);

    expect(screen.getByText(/1 . Initial validation batch \(up to 5 documents\)/)).toBeDefined();
    expect(screen.getByText(/2 . Large batch \(100\+ documents, no review needed\)/)).toBeDefined();
    expect(screen.getByText(/Locked until the initial validation batch above is approved/)).toBeDefined();
    expect(screen.queryByRole("radio")).toBeNull();
  });

  it("keeps the approved initial batch's status visible while unlocking the large-batch picker", () => {
    mockUsePrelabelBatches.mockReturnValue(
      batchesResult([
        {
          batch_id: "b1",
          batch_kind: "initial",
          state: "completed",
          annotator_review_status: "approved",
          acceptance_decision: "accepted",
        },
      ]),
    );
    mockUsePrelabelBatch.mockImplementation((id: string | null) => {
      if (id === "b1") return batchDetail({ batch_id: "b1", annotator_review_status: "approved" });
      return { data: undefined };
    });

    render(<BatchAcceptancePage />);

    // Stage 1's own approval confirmation is still shown, not replaced by stage 2.
    expect(screen.getByText("✓ Reviewed and approved by an Annotator Admin")).toBeDefined();
    // Stage 2 is unlocked: its picker shows instead of the locked message.
    expect(screen.queryByText(/Locked until/)).toBeNull();
    expect(screen.getByText("a.pdf")).toBeDefined();
  });

  it("does not unlock stage 2 while the initial batch is unreviewed", () => {
    mockUsePrelabelBatches.mockReturnValue(
      batchesResult([{ batch_id: "b1", batch_kind: "initial", state: "completed", annotator_review_status: null }]),
    );
    mockUsePrelabelBatch.mockImplementation((id: string | null) => {
      if (id === "b1") return batchDetail({ batch_id: "b1", annotator_review_status: null });
      return { data: undefined };
    });

    render(<BatchAcceptancePage />);

    expect(screen.getByText(/With an Annotator Admin for review/)).toBeDefined();
    expect(screen.getByText(/Locked until the initial validation batch above is approved/)).toBeDefined();
  });

  it("shows a Train model action once the large batch finishes, alongside the initial batch's own status", () => {
    mockUsePrelabelBatches.mockReturnValue(
      batchesResult([
        { batch_id: "b2", batch_kind: "large", state: "completed", annotator_review_status: "approved" },
        { batch_id: "b1", batch_kind: "initial", state: "completed", annotator_review_status: "approved" },
      ]),
    );
    mockUsePrelabelBatch.mockImplementation((id: string | null) => {
      if (id === "b1") return batchDetail({ batch_id: "b1", annotator_review_status: "approved" });
      if (id === "b2") return batchDetail({ batch_id: "b2", annotator_review_status: "approved" });
      return { data: undefined };
    });

    render(<BatchAcceptancePage />);

    // Both stages' confirmations are visible at the same time.
    expect(screen.getByText("✓ Reviewed and approved by an Annotator Admin")).toBeDefined();
    expect(screen.getByText("✓ Completed — promoted automatically, training eligible")).toBeDefined();
    // The upload option for another large batch stays available — a completed batch already
    // existing must not hide it or make it look like there's "nothing to do."
    expect(screen.getByText("Most recent large batch")).toBeDefined();
    expect(screen.getByText("Pre-label these documents")).toBeDefined();
    expect(screen.getByText("a.pdf")).toBeDefined();

    const cta = screen.getByText("Train model →");
    fireEvent.click(cta);
    expect(mockPush).toHaveBeenCalledWith("/training-jobs?source=automated");
    expect(screen.queryByText("Start acceptance review")).toBeNull();
    expect(screen.queryByText("Confirm whole batch")).toBeNull();
  });

  it("disables starting another large batch while one is already running, but keeps the picker visible", () => {
    mockUsePrelabelBatches.mockReturnValue(
      batchesResult([
        { batch_id: "b2", batch_kind: "large", state: "processing", annotator_review_status: null },
        { batch_id: "b1", batch_kind: "initial", state: "completed", annotator_review_status: "approved" },
      ]),
    );
    mockUsePrelabelBatch.mockImplementation((id: string | null) => {
      if (id === "b1") return batchDetail({ batch_id: "b1", annotator_review_status: "approved" });
      if (id === "b2") return batchDetail({ batch_id: "b2", state: "processing", status: "running", annotator_review_status: null });
      return { data: undefined };
    });

    render(<BatchAcceptancePage />);

    expect(screen.getByText("Pre-label these documents")).toBeDefined();
    expect(screen.getByText(/already running/)).toBeDefined();
  });

  it("tells the admin no review is needed while the large batch is still processing", () => {
    mockUsePrelabelBatches.mockReturnValue(
      batchesResult([
        { batch_id: "b2", batch_kind: "large", state: "processing", annotator_review_status: null },
        { batch_id: "b1", batch_kind: "initial", state: "completed", annotator_review_status: "approved" },
      ]),
    );
    mockUsePrelabelBatch.mockImplementation((id: string | null) => {
      if (id === "b1") return batchDetail({ batch_id: "b1", annotator_review_status: "approved" });
      if (id === "b2")
        return batchDetail({
          batch_id: "b2",
          state: "processing",
          status: "running",
          succeeded: 40,
          progress: { settled: 40, total: 150 },
          annotator_review_status: null,
        });
      return { data: undefined };
    });

    render(<BatchAcceptancePage />);

    expect(screen.getByText(/no review is needed once it finishes/)).toBeDefined();
    expect(screen.queryByText("Train model →")).toBeNull();
  });

  it("toasts exactly once, on the transition to annotator-approved — not on every render", () => {
    mockUsePrelabelBatches.mockReturnValue(
      batchesResult([{ batch_id: "b1", batch_kind: "initial", state: "completed", annotator_review_status: null }]),
    );
    mockUsePrelabelBatch.mockImplementation((id: string | null) => {
      if (id === "b1") return batchDetail({ batch_id: "b1", annotator_review_status: null });
      return { data: undefined };
    });

    const { rerender } = render(<BatchAcceptancePage />);
    expect(mockToast).not.toHaveBeenCalled();

    // Re-render with the same "not yet approved" data — must not toast just from rendering
    // again.
    rerender(<BatchAcceptancePage />);
    expect(mockToast).not.toHaveBeenCalled();

    // Now the batch transitions to approved.
    mockUsePrelabelBatch.mockImplementation((id: string | null) => {
      if (id === "b1") return batchDetail({ batch_id: "b1", annotator_review_status: "approved" });
      return { data: undefined };
    });
    rerender(<BatchAcceptancePage />);
    expect(mockToast).toHaveBeenCalledTimes(1);
    expect(mockToast).toHaveBeenCalledWith(
      "Initial validation batch reviewed and approved by an Annotator Admin.",
      "ok",
    );

    // Staying approved on a further render must not toast again.
    rerender(<BatchAcceptancePage />);
    expect(mockToast).toHaveBeenCalledTimes(1);
  });
});
