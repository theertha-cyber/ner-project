/**
 * Cardinality, value kind, and the base-label mapping the projection routes on.
 *
 * `cardinality` decides which generated relation holds an entity type's values, so it is the
 * one control in this form whose wrong setting is invisible: a multi-valued entity marked
 * `single` keeps extracting normally while every value but one disappears from the query
 * surface. That is why the persisted value has to be reflected in edit mode rather than reset
 * to a default, and why changing it on an existing entity type asks first.
 *
 * Covers verification.md rows 126-132, 136-143.
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

describe("cardinality control", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue(okResponse());
  });

  it("defaults to Multiple values in create mode", () => {
    render(<DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={null} />, {
      wrapper: createWrapper(),
    });
    expect(option("Multiple values").getAttribute("aria-pressed")).toBe("true");
    expect(option("Single value").getAttribute("aria-pressed")).toBe("false");
  });

  it("reflects the persisted cardinality in edit mode", () => {
    render(
      <DefineEntityTypeSlideOver
        open={true}
        onClose={vi.fn()}
        editTarget={entityType({ cardinality: "single" })}
      />,
      { wrapper: createWrapper() },
    );
    // Rendering the default here instead would silently reset the field on every save.
    expect(option("Single value").getAttribute("aria-pressed")).toBe("true");
  });

  it("is single-select", () => {
    render(<DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={null} />, {
      wrapper: createWrapper(),
    });
    fireEvent.click(option("Single value"));
    expect(option("Single value").getAttribute("aria-pressed")).toBe("true");
    expect(option("Multiple values").getAttribute("aria-pressed")).toBe("false");
  });

  it("submits the selected cardinality on create", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ id: "et-new" }), { status: 201 }),
    );
    render(<DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={null} />, {
      wrapper: createWrapper(),
    });

    fireEvent.change(screen.getByPlaceholderText("vendor_name"), {
      target: { value: "candidate_email" },
    });
    fireEvent.click(option("Single value"));
    fireEvent.click(screen.getByRole("button", { name: "Create entity type" }));

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    expect(lastBody().cardinality).toBe("single");
  });

  it("round-trips an unchanged cardinality on edit", async () => {
    const onClose = vi.fn();
    render(
      <DefineEntityTypeSlideOver open={true} onClose={onClose} editTarget={entityType()} />,
      { wrapper: createWrapper() },
    );

    fireEvent.change(screen.getByPlaceholderText("Name of a vendor / supplier"), {
      target: { value: "changed" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(lastBody().cardinality).toBe("multi");
  });
});

describe("value kind control", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue(okResponse());
  });

  it("defaults to text in create mode and submits it", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ id: "et-new" }), { status: 201 }),
    );
    render(<DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={null} />, {
      wrapper: createWrapper(),
    });

    expect((screen.getByLabelText("Value Kind") as HTMLSelectElement).value).toBe("text");

    fireEvent.change(screen.getByPlaceholderText("vendor_name"), {
      target: { value: "skill" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create entity type" }));

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    expect(lastBody().value_kind).toBe("text");
  });

  it("reflects the persisted value kind in edit mode", () => {
    render(
      <DefineEntityTypeSlideOver
        open={true}
        onClose={vi.fn()}
        editTarget={entityType({ value_kind: "number" })}
      />,
      { wrapper: createWrapper() },
    );
    // Without this the typed `subject` column a `single` entity type exists for is
    // unreachable: every save would push it back to `text`.
    expect((screen.getByLabelText("Value Kind") as HTMLSelectElement).value).toBe("number");
  });

  it("submits a changed value kind on edit", async () => {
    const onClose = vi.fn();
    render(
      <DefineEntityTypeSlideOver open={true} onClose={onClose} editTarget={entityType()} />,
      { wrapper: createWrapper() },
    );

    fireEvent.change(screen.getByLabelText("Value Kind"), { target: { value: "number" } });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(lastBody().value_kind).toBe("number");
  });
});

describe("sql_identifier is never submitted", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue(okResponse());
  });

  it("is absent from the create body", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ id: "et-new" }), { status: 201 }),
    );
    render(<DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={null} />, {
      wrapper: createWrapper(),
    });
    fireEvent.change(screen.getByPlaceholderText("vendor_name"), {
      target: { value: "skill" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create entity type" }));

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    expect(lastBody()).not.toHaveProperty("sql_identifier");
  });

  it("is absent from the edit body even though the loaded entity carries one", async () => {
    const onClose = vi.fn();
    render(
      <DefineEntityTypeSlideOver open={true} onClose={onClose} editTarget={entityType()} />,
      { wrapper: createWrapper() },
    );
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(lastBody()).not.toHaveProperty("sql_identifier");
  });
});

describe("base label mapping preservation", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue(okResponse());
  });

  const multiKey = entityType({
    name: "employer",
    base_label_mapping: { ORG: ["employer"], MISC: ["employer"] },
  });

  it("keeps every persisted key across an unrelated edit", async () => {
    const onClose = vi.fn();
    render(
      <DefineEntityTypeSlideOver open={true} onClose={onClose} editTarget={multiKey} />,
      { wrapper: createWrapper() },
    );

    fireEvent.change(screen.getByPlaceholderText("Name of a vendor / supplier"), {
      target: { value: "changed" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    // The projection routes on the full key set, so a dropped key removes a base-model label
    // from the routing index and empties part of that tenant's query surface with no error.
    const mapping = lastBody().base_label_mapping;
    expect(Object.keys(mapping).sort()).toEqual(["MISC", "ORG"]);
  });

  it("shows one chip selected while still submitting the keys the chip row cannot show", async () => {
    const onClose = vi.fn();
    render(
      <DefineEntityTypeSlideOver open={true} onClose={onClose} editTarget={multiKey} />,
      { wrapper: createWrapper() },
    );

    expect(screen.getByRole("button", { name: "ORG" }).getAttribute("aria-pressed")).toBe(
      "true",
    );

    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(lastBody().base_label_mapping).toHaveProperty("MISC");
  });

  it("still applies a chip change on top of the persisted mapping", async () => {
    const onClose = vi.fn();
    render(
      <DefineEntityTypeSlideOver open={true} onClose={onClose} editTarget={multiKey} />,
      { wrapper: createWrapper() },
    );

    fireEvent.click(screen.getByRole("button", { name: "LOC" }));
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(Object.keys(lastBody().base_label_mapping).sort()).toEqual([
      "LOC",
      "MISC",
      "ORG",
    ]);
  });
});

describe("cardinality change confirmation", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue(okResponse());
  });

  it("asks before changing multi to single, and says what stays behind", async () => {
    render(
      <DefineEntityTypeSlideOver open={true} onClose={vi.fn()} editTarget={entityType()} />,
      { wrapper: createWrapper() },
    );

    fireEvent.click(option("Single value"));
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    const dialog = await screen.findByRole("dialog", { name: "Confirm cardinality change" });
    expect(dialog.textContent).toContain("stay where they are");
    expect(dialog.textContent).toContain("re-extracted");
    // Nothing is sent until the admin confirms.
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("asks before changing single to multi", async () => {
    render(
      <DefineEntityTypeSlideOver
        open={true}
        onClose={vi.fn()}
        editTarget={entityType({ cardinality: "single" })}
      />,
      { wrapper: createWrapper() },
    );

    fireEvent.click(option("Multiple values"));
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    const dialog = await screen.findByRole("dialog", { name: "Confirm cardinality change" });
    expect(dialog.textContent).toContain("one value per document");
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("sends the update on confirm", async () => {
    const onClose = vi.fn();
    render(
      <DefineEntityTypeSlideOver open={true} onClose={onClose} editTarget={entityType()} />,
      { wrapper: createWrapper() },
    );

    fireEvent.click(option("Single value"));
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    fireEvent.click(await screen.findByRole("button", { name: "Change cardinality" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(mockFetch.mock.calls[0][1]?.method).toBe("PUT");
    expect(lastBody().cardinality).toBe("single");
  });

  it("sends nothing on cancel and keeps the new selection showing", async () => {
    const onClose = vi.fn();
    render(
      <DefineEntityTypeSlideOver open={true} onClose={onClose} editTarget={entityType()} />,
      { wrapper: createWrapper() },
    );

    fireEvent.click(option("Single value"));
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));
    fireEvent.click(await screen.findByRole("button", { name: "Cancel" }));

    expect(mockFetch).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
    expect(option("Single value").getAttribute("aria-pressed")).toBe("true");
  });

  it("does not prompt when cardinality is unchanged", async () => {
    const onClose = vi.fn();
    render(
      <DefineEntityTypeSlideOver open={true} onClose={onClose} editTarget={entityType()} />,
      { wrapper: createWrapper() },
    );

    fireEvent.change(screen.getByPlaceholderText("Name of a vendor / supplier"), {
      target: { value: "changed" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(
      screen.queryByRole("dialog", { name: "Confirm cardinality change" }),
    ).toBeNull();
  });

  it("never prompts in create mode", async () => {
    mockFetch.mockResolvedValue(
      new Response(JSON.stringify({ id: "et-new" }), { status: 201 }),
    );
    const onClose = vi.fn();
    render(<DefineEntityTypeSlideOver open={true} onClose={onClose} editTarget={null} />, {
      wrapper: createWrapper(),
    });

    fireEvent.change(screen.getByPlaceholderText("vendor_name"), {
      target: { value: "skill" },
    });
    fireEvent.click(option("Single value"));
    fireEvent.click(screen.getByRole("button", { name: "Create entity type" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    expect(
      screen.queryByRole("dialog", { name: "Confirm cardinality change" }),
    ).toBeNull();
  });
});
