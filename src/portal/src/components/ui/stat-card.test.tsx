import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatCard } from "./stat-card";

describe("StatCard", () => {
  it("applies delta-up colour class for deltaDir=up", () => {
    render(<StatCard label="F1 Score" value="0.91" delta="+0.03" deltaDir="up" />);
    const delta = screen.getByTestId("delta");
    expect(delta).toHaveClass("text-delta-up");
  });

  it("applies delta-warn colour class for deltaDir=warn", () => {
    render(<StatCard label="Errors" value="12" delta="+5" deltaDir="warn" />);
    const delta = screen.getByTestId("delta");
    expect(delta).toHaveClass("text-delta-warn");
  });

  it("renders no delta element when delta prop is absent", () => {
    render(<StatCard label="Tenants" value="7" />);
    expect(screen.queryByTestId("delta")).not.toBeInTheDocument();
  });

  it("applies shadow-card class to the card container", () => {
    const { container } = render(<StatCard label="Models" value="3" />);
    expect(container.firstChild).toHaveClass("shadow-card");
  });

  it("renders label and value", () => {
    render(<StatCard label="Documents" value="42" />);
    expect(screen.getByText("Documents")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });
});
