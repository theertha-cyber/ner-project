import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { SearchableCombobox } from "./searchable-combobox";

const options = [
  { value: "all", label: "All Tenants" },
  { value: "acme", label: "Acme Corp" },
  { value: "globex", label: "Globex Inc" },
];

describe("SearchableCombobox", () => {
  it("typing filters the visible options", async () => {
    render(<SearchableCombobox value="all" onChange={vi.fn()} options={options} ariaLabel="Tenant filter" />);
    const input = screen.getByRole("combobox", { name: "Tenant filter" });
    await userEvent.click(input);
    await userEvent.type(input, "acme");

    expect(screen.getByRole("option", { name: "Acme Corp" })).toBeInTheDocument();
    expect(screen.queryByRole("option", { name: "Globex Inc" })).not.toBeInTheDocument();
  });

  it("selecting an option calls onChange and closes the dropdown", async () => {
    const onChange = vi.fn();
    render(<SearchableCombobox value="all" onChange={onChange} options={options} ariaLabel="Tenant filter" />);
    const input = screen.getByRole("combobox", { name: "Tenant filter" });
    await userEvent.click(input);
    await userEvent.click(screen.getByRole("option", { name: "Acme Corp" }));

    expect(onChange).toHaveBeenCalledWith("acme");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("clicking outside closes the dropdown", async () => {
    render(
      <div>
        <SearchableCombobox value="all" onChange={vi.fn()} options={options} ariaLabel="Tenant filter" />
        <button>outside</button>
      </div>
    );
    const input = screen.getByRole("combobox", { name: "Tenant filter" });
    await userEvent.click(input);
    expect(screen.getByRole("listbox")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "outside" }));
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });
});
