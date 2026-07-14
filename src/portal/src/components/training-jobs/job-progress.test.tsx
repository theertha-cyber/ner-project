import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { JobProgress } from "./job-progress";

describe("JobProgress", () => {
  it("renders the live callout for a running job with correct epoch fraction and stat row", () => {
    render(<JobProgress currentEpoch={2} currentLoss={0.032} numEpochs={3} />);

    expect(screen.getByTestId("job-progress-callout")).toBeDefined();
    expect(screen.getByText("Fine-tuning in progress")).toBeDefined();
    expect(screen.getByText("epoch 2/3")).toBeDefined();
    expect(screen.getByText("loss 0.0320")).toBeDefined();
    expect(screen.getByText("epoch 2.0")).toBeDefined();
    expect(screen.getByText("GPU worker-2")).toBeDefined();

    const bar = document.querySelector('[style*="width"]') as HTMLElement;
    expect(bar).not.toBeNull();
    expect(bar.style.width).toBe("66.66666666666666%");
  });

  it("renders no callout when currentEpoch is null (non-running job)", () => {
    render(<JobProgress currentEpoch={null} currentLoss={null} numEpochs={3} />);
    expect(screen.queryByTestId("job-progress-callout")).toBeNull();
  });
});
