import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { SafeOutcomeNotice, SafeStatusBadge } from "./status";

describe("SafeStatusBadge", () => {
  it.each([["draft", "Draft"], ["validated", "Validated"], ["active", "Active"], ["paused", "Paused"], ["error", "Error"], ["retired", "Retired"]] as const)(
    "labels status %s as text, not colour alone",
    (status, label) => {
      render(<SafeStatusBadge status={status} />);
      expect(screen.getByRole("status", { name: `Status: ${label}` })).toHaveTextContent(label);
    },
  );
});

describe("SafeOutcomeNotice", () => {
  it("renders finite code and request ID with an alert role for errors", () => {
    render(<SafeOutcomeNotice variant="error" title="Activation blocked" code="ACTIVATION_PREREQUISITE_MISSING" requestId="req-1" />);
    const notice = screen.getByRole("alert", { name: "Activation blocked" });
    expect(notice).toHaveTextContent("ACTIVATION_PREREQUISITE_MISSING");
    expect(notice).toHaveTextContent("req-1");
  });

  it("refuses dismissal for blocking notices", async () => {
    const user = userEvent.setup();
    render(<SafeOutcomeNotice variant="blocked" title="Prerequisites missing" code="TEST_REQUIRED" />);
    expect(screen.queryByRole("button", { name: "Dismiss notice" })).not.toBeInTheDocument();
    expect(screen.getByRole("alert", { name: "Prerequisites missing" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.getByRole("alert", { name: "Prerequisites missing" })).toBeInTheDocument();
  });

  it("dismisses non-blocking notices and announces replay", async () => {
    const user = userEvent.setup();
    render(<SafeOutcomeNotice variant="success" title="Test passed" code="TEST_PASSED" replayed />);
    expect(screen.getByText(/Replayed safely/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Dismiss notice" }));
    expect(screen.queryByRole("status", { name: "Test passed" })).not.toBeInTheDocument();
  });
});
