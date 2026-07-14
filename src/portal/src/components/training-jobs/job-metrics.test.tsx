import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { JobMetrics } from "./job-metrics";

describe("JobMetrics", () => {
  it("renders f1/precision/recall as large stat numbers with mini progress bars, and eval_loss separately", () => {
    render(
      <JobMetrics
        metrics={{ eval_f1: 0.9, eval_precision: 0.92, eval_recall: 0.89, eval_loss: 0.021 }}
      />,
    );

    expect(screen.getByText("0.90")).toBeDefined();
    expect(screen.getByText("0.92")).toBeDefined();
    expect(screen.getByText("0.89")).toBeDefined();
    expect(screen.getByText("f1")).toBeDefined();
    expect(screen.getByText("precision")).toBeDefined();
    expect(screen.getByText("recall")).toBeDefined();
    expect(screen.getByText("eval_loss 0.021")).toBeDefined();
  });

  it("returns null when no relevant metrics are present", () => {
    const { container } = render(<JobMetrics metrics={{ PERSON_f1: 0.5 }} />);
    expect(container.firstChild).toBeNull();
  });
});
