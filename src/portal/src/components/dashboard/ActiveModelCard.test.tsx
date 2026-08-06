import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ActiveModelCard } from "./ActiveModelCard";
import type { ActiveModelInfo } from "@/types/dashboard";

describe("ActiveModelCard", () => {
  it("renders model identifier, status, version, and deployed date", () => {
    const data: ActiveModelInfo = {
      name: "run-003-20260805",
      status: "active",
      version: "v3",
      deployedAt: "5 Aug 2026",
    };
    render(<ActiveModelCard data={data} />);
    expect(screen.getByText("Active Model")).toBeInTheDocument();
    expect(screen.getByText("run-003-20260805")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("v3")).toBeInTheDocument();
    expect(screen.getByText("5 Aug 2026")).toBeInTheDocument();
  });

  it("does not render any performance metrics, percentages, or charts", () => {
    const data: ActiveModelInfo = {
      name: "run-003-20260805",
      status: "active",
      version: "v3",
      deployedAt: "5 Aug 2026",
    };
    render(<ActiveModelCard data={data} />);
    expect(screen.queryByText(/f1/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/precision/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/recall/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/loss/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it("renders placeholder state when no model data is available", () => {
    render(<ActiveModelCard data={null} />);
    expect(screen.getByText("Active Model")).toBeInTheDocument();
    expect(screen.getByText("Unavailable")).toBeInTheDocument();
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });
});
