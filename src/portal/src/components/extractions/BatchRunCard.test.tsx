/**
 * Covers verification.md row 108.
 *
 * A run that completed because the fail-open path kept the BERT result must not read the
 * same as one where post-processing actually ran — otherwise the degraded data is
 * indistinguishable from the intended data.
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { BatchRunCard } from "./BatchRunCard";
import type { BatchRun } from "@/types/extraction";

const BASE: BatchRun = {
  run_id: "run-mode-1",
  status: "completed",
  total_documents: 4,
  processed_count: 4,
  started_at: "2026-08-14T09:00:00Z",
};

function renderCard(run: BatchRun) {
  return render(<BatchRunCard run={run} isSelected={false} onClick={vi.fn()} />);
}

describe("BatchRunCard processing mode", () => {
  it("labels a BERT-only run", () => {
    renderCard({ ...BASE, processing_mode: "bert_only" });

    expect(screen.getByTestId("processing-mode")).toHaveTextContent("BERT");
  });

  it("labels a post-processed run distinctly", () => {
    renderCard({ ...BASE, processing_mode: "bert_llm_postprocess" });

    expect(screen.getByTestId("processing-mode")).toHaveTextContent("BERT + LLM");
  });

  it("marks a degraded run visually distinct from a clean one", () => {
    const { unmount } = renderCard({
      ...BASE,
      processing_mode: "bert_llm_postprocess",
      postprocess_degraded: true,
    });
    const degraded = screen.getByTestId("processing-mode");
    expect(degraded).toHaveTextContent(/degraded/i);
    const degradedClass = degraded.className;
    unmount();

    renderCard({
      ...BASE,
      processing_mode: "bert_llm_postprocess",
      postprocess_degraded: false,
    });
    const clean = screen.getByTestId("processing-mode");
    expect(clean).not.toHaveTextContent(/degraded/i);
    expect(clean.className).not.toEqual(degradedClass);
  });

  it("renders no mode label for a run that predates the field", () => {
    renderCard(BASE);

    expect(screen.queryByTestId("processing-mode")).toBeNull();
  });

  it("still renders status and progress alongside the mode", () => {
    renderCard({ ...BASE, processing_mode: "bert_only" });

    expect(screen.getByText("completed")).toBeTruthy();
    expect(screen.getByText(/100% docs/)).toBeTruthy();
  });
});
