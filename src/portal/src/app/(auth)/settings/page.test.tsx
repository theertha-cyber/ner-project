import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import SettingsPage from "./page";

describe("SettingsPage", () => {
  it("renders the settings heading without coming-soon copy", () => {
    render(<SettingsPage />);

    expect(screen.getByRole("heading", { name: "Settings" })).toBeInTheDocument();
    expect(screen.queryByText("This screen is coming soon.")).not.toBeInTheDocument();
  });
});
