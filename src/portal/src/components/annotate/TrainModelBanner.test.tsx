import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TrainModelBanner } from "./TrainModelBanner";

describe("TrainModelBanner", () => {
  it("renders nothing when zero documents are annotated", () => {
    const { container } = render(<TrainModelBanner annotatedCount={0} onTrain={vi.fn()} />);
    expect(container.firstChild).toBeNull();
  });

  it("shows the singular form for exactly one annotated document", () => {
    render(<TrainModelBanner annotatedCount={1} onTrain={vi.fn()} />);
    expect(screen.getByText(/1 document annotated and ready for training\./)).toBeDefined();
  });

  it("shows the plural form and the real count for multiple documents", () => {
    render(<TrainModelBanner annotatedCount={99} onTrain={vi.fn()} />);
    expect(screen.getByText(/99 documents annotated and ready for training\./)).toBeDefined();
  });

  it("calls onTrain when the CTA is activated", () => {
    const onTrain = vi.fn();
    render(<TrainModelBanner annotatedCount={5} onTrain={onTrain} />);
    fireEvent.click(screen.getByText("Train model →"));
    expect(onTrain).toHaveBeenCalledTimes(1);
  });
});
