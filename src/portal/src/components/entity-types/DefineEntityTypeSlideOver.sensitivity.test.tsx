/**
 * Sensitivity classification: `open` (default), `pattern` (requires a validation_rule the
 * client checks before submit, mirroring the backend's own 422), and `local_only` (no extra
 * configuration). This field is inert until `automated-annotation-pii-masking` reads it — this
 * test file only covers the form, not any pre-labeling behavior.
 *
 * Covers the `entity-sensitivity-classification` change's spec scenarios for this field.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "@/hooks/use-toast";
import { DefineEntityTypeSlideOver } from "./DefineEntityTypeSlideOver";
import type { EntityType } from "@/types/entity-types";

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({ user: { tenantSlug: "acme-corp" } }),
}));

const mockFetch = vi.fn();
globalThis.fetch = mockFetch;

function createWrapper() {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <ToastProvider>{children}</ToastProvider>
      </QueryClientProvider>
    );
  };
}

function entityType(overrides: Partial<EntityType> = {}): EntityType {
  return {
    id: "et-1",
    name: "vendor_name",
    description: "Name of a vendor",
    examples: ["Northwind Logistics"],
    base_label_mapping: { ORG: ["vendor_name"] },
    target_table: null,
    required_flag: false,
    is_active: true,
    version: 1,
    cardinality: "multi",
    value_kind: "text",
    sql_identifier: "e_vendor_name",
    sensitivity: "open",
    validation_rule: null,
    ...overrides,
  };
}

function okResponse() {
  return new Response(JSON.stringify({ id: "et-1", name: "vendor_name", version: 2 }), {
    status: 200,
  });
}

function lastBody() {
  const call = mockFetch.mock.calls[mockFetch.mock.calls.length - 1];
  return JSON.parse(String(call[1]?.body));
}

function option(label: string) {
  return screen.getByText(label).closest("button") as HTMLButtonElement;
}

describe("sensitivity control", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue(okResponse());
  });

  it("defaults to Open in create mode", () => {
    render(<DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={null} />, {
      wrapper: createWrapper(),
    });
    expect(option("Open").getAttribute("aria-pressed")).toBe("true");
    expect(option("Pattern").getAttribute("aria-pressed")).toBe("false");
    expect(option("Local only").getAttribute("aria-pressed")).toBe("false");
  });

  it("reflects the persisted sensitivity in edit mode", () => {
    render(
      <DefineEntityTypeSlideOver
        open={true}
        onClose={vi.fn()}
        editTarget={entityType({ sensitivity: "local_only" })}
      />,
      { wrapper: createWrapper() },
    );
    expect(option("Local only").getAttribute("aria-pressed")).toBe("true");
  });

  it("is single-select", () => {
    render(<DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={null} />, {
      wrapper: createWrapper(),
    });
    fireEvent.click(option("Local only"));
    expect(option("Local only").getAttribute("aria-pressed")).toBe("true");
    expect(option("Open").getAttribute("aria-pressed")).toBe("false");
  });

  it("submits open with no validation_rule required", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ id: "et-new" }), { status: 201 }));
    render(<DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={null} />, {
      wrapper: createWrapper(),
    });

    fireEvent.change(screen.getByPlaceholderText("vendor_name"), {
      target: { value: "customer_name" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create entity type" }));

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    expect(lastBody().sensitivity).toBe("open");
    expect(lastBody().validation_rule).toBeNull();
  });

  it("submits local_only with no validation_rule required", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ id: "et-new" }), { status: 201 }));
    render(<DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={null} />, {
      wrapper: createWrapper(),
    });

    fireEvent.change(screen.getByPlaceholderText("vendor_name"), {
      target: { value: "child_name" },
    });
    fireEvent.click(option("Local only"));
    fireEvent.click(screen.getByRole("button", { name: "Create entity type" }));

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    expect(lastBody().sensitivity).toBe("local_only");
  });

  it("blocks submit when pattern is selected with no pattern entered", async () => {
    render(<DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={null} />, {
      wrapper: createWrapper(),
    });

    fireEvent.change(screen.getByPlaceholderText("vendor_name"), {
      target: { value: "ssn" },
    });
    fireEvent.click(option("Pattern"));
    fireEvent.click(screen.getByRole("button", { name: "Create entity type" }));

    expect(
      await screen.findByText("Pattern sensitivity requires a pattern to match against."),
    ).toBeInTheDocument();
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("reveals a pattern input only when Pattern is selected", () => {
    render(<DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={null} />, {
      wrapper: createWrapper(),
    });

    expect(screen.queryByLabelText("Pattern (regex)")).toBeNull();
    fireEvent.click(option("Pattern"));
    expect(screen.getByLabelText("Pattern (regex)")).toBeInTheDocument();
  });

  it("submits pattern with its validation_rule once filled in", async () => {
    mockFetch.mockResolvedValue(new Response(JSON.stringify({ id: "et-new" }), { status: 201 }));
    render(<DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={null} />, {
      wrapper: createWrapper(),
    });

    fireEvent.change(screen.getByPlaceholderText("vendor_name"), {
      target: { value: "ssn" },
    });
    fireEvent.click(option("Pattern"));
    fireEvent.change(screen.getByLabelText("Pattern (regex)"), {
      target: { value: "^\\d{3}-\\d{2}-\\d{4}$" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create entity type" }));

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    expect(lastBody().sensitivity).toBe("pattern");
    expect(lastBody().validation_rule).toBe("^\\d{3}-\\d{2}-\\d{4}$");
  });

  it("round-trips an unchanged sensitivity on edit", async () => {
    const onClose = vi.fn();
    render(
      <DefineEntityTypeSlideOver
        open={true}
        onClose={onClose}
        editTarget={entityType({ sensitivity: "pattern", validation_rule: "\\d{3}" })}
      />,
      { wrapper: createWrapper() },
    );

    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(lastBody().sensitivity).toBe("pattern");
    expect(lastBody().validation_rule).toBe("\\d{3}");
  });
});
