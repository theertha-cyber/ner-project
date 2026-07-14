import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LineageFlow } from "./LineageFlow";

describe("LineageFlow", () => {
  it("renders N boxes with labels and values", () => {
    render(
      <LineageFlow
        nodes={[
          { label: "DATASET", value: "invoices-v3" },
          { label: "TRAINING JOB", value: "tj_7c04" },
          { label: "MODEL VERSION", value: "v3" },
        ]}
      />,
    );
    expect(screen.getAllByTestId("lineage-node")).toHaveLength(3);
    expect(screen.getByText("invoices-v3")).toBeDefined();
    expect(screen.getByText("tj_7c04")).toBeDefined();
    expect(screen.getByText("v3")).toBeDefined();
    expect(screen.getByText("DATASET")).toBeDefined();
    expect(screen.getByText("TRAINING JOB")).toBeDefined();
    expect(screen.getByText("MODEL VERSION")).toBeDefined();
  });

  it("renders arrows between boxes", () => {
    render(
      <LineageFlow
        nodes={[
          { label: "A", value: "1" },
          { label: "B", value: "2" },
          { label: "C", value: "3" },
        ]}
      />,
    );
    expect(screen.getAllByTestId("lineage-arrow")).toHaveLength(2);
  });

  it("applies emphasis styling to the specified index", () => {
    render(
      <LineageFlow
        nodes={[
          { label: "A", value: "1" },
          { label: "B", value: "2" },
          { label: "C", value: "3" },
        ]}
        emphasizedIndex={1}
      />,
    );
    const nodesEls = screen.getAllByTestId("lineage-node");
    expect(nodesEls[0].dataset.emphasized).toBe("false");
    expect(nodesEls[1].dataset.emphasized).toBe("true");
    expect(nodesEls[2].dataset.emphasized).toBe("false");
  });

  it("renders a fallback value when a node's value is null or undefined", () => {
    render(
      <LineageFlow
        nodes={[
          { label: "DATASET", value: "invoices-v4" },
          { label: "TRAINING JOB", value: "tj_9f2a" },
          { label: "MODEL VERSION", value: null },
        ]}
      />,
    );
    expect(screen.getByText("pending")).toBeDefined();
  });
});
