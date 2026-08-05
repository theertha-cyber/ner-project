import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ResponseQualityCard } from "./ResponseQualityCard";
import type { ResponseQuality } from "@/types/dashboard";

describe("ResponseQualityCard", () => {
  it("renders Healthy status with headline, sample size, and positive recommendation", () => {
    const data: ResponseQuality = {
      status: "healthy",
      satisfactionPct: 92,
      positive: 46,
      negative: 4,
      rated: 50,
      total: 320,
      recommendation: "No retraining recommended. Business users are consistently rating responses positively.",
    };
    render(<ResponseQualityCard data={data} />);
    expect(screen.getByText("Response Quality")).toBeInTheDocument();
    expect(screen.getByText("Healthy")).toBeInTheDocument();
    expect(screen.getByText("92%")).toBeInTheDocument();
    expect(screen.getByText("Positive Feedback")).toBeInTheDocument();
    expect(screen.getByText("46 of 50 reviewed responses were positive")).toBeInTheDocument();
    expect(screen.getByText("Business User Feedback")).toBeInTheDocument();
    expect(screen.getByText("46")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("50 of 320 AI responses reviewed")).toBeInTheDocument();
    expect(screen.getByText(/No retraining recommended/)).toBeInTheDocument();
  });

  it("renders Needs Attention status with a retraining recommendation", () => {
    const data: ResponseQuality = {
      status: "needs_attention",
      satisfactionPct: 33,
      positive: 1,
      negative: 2,
      rated: 3,
      total: 70,
      recommendation: "Consider retraining the model. Business users are reporting low response quality.",
    };
    render(<ResponseQualityCard data={data} />);
    expect(screen.getByText("Needs Attention")).toBeInTheDocument();
    expect(screen.getByText("33%")).toBeInTheDocument();
    expect(screen.getByText("1 of 3 reviewed responses were positive")).toBeInTheDocument();
    expect(screen.getByText("3 of 70 AI responses reviewed")).toBeInTheDocument();
    expect(screen.getByText(/Consider retraining the model/)).toBeInTheDocument();
  });

  it("renders Monitor status", () => {
    const data: ResponseQuality = {
      status: "monitor",
      satisfactionPct: 70,
      positive: 7,
      negative: 3,
      rated: 10,
      total: 40,
      recommendation: "Keep an eye on response quality. Consider gathering more feedback before deciding on retraining.",
    };
    render(<ResponseQualityCard data={data} />);
    expect(screen.getByText("Monitor")).toBeInTheDocument();
    expect(screen.getByText("70%")).toBeInTheDocument();
  });

  it("renders a no-data state without a misleading percentage when nothing has been rated", () => {
    const data: ResponseQuality = {
      status: "no_data",
      satisfactionPct: null,
      positive: 0,
      negative: 0,
      rated: 0,
      total: 12,
      recommendation: "Not enough feedback yet to assess model performance.",
    };
    render(<ResponseQualityCard data={data} />);
    expect(screen.getByText("Not Enough Data")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.getByText("No responses have been reviewed yet")).toBeInTheDocument();
    expect(screen.getByText("0 of 12 AI responses reviewed")).toBeInTheDocument();
    expect(screen.getByText(/Not enough feedback yet/)).toBeInTheDocument();
  });
});
