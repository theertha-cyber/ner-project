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
    name: "years_experience",
    description: "Years of experience",
    examples: ["10 years"],
    base_label_mapping: { MISC: ["years_experience"] },
    target_table: null,
    required_flag: false,
    is_active: true,
    version: 1,
    cardinality: "single",
    value_kind: "number",
    sql_identifier: "e_years_experience",
    ...overrides,
  };
}

function okResponse(status = 200) {
  return { ok: true, status, json: async () => ({}) };
}

function lastRequestBody() {
  const call = mockFetch.mock.calls.at(-1);
  return JSON.parse(call![1].body as string);
}

describe("DefineEntityTypeSlideOver — QA pairs", () => {
  beforeEach(() => {
    mockFetch.mockReset();
    mockFetch.mockResolvedValue(okResponse());
  });

  // Spec Alignment row 19
  it("prefills_existing_qa_pairs", () => {
    const target = entityType({
      qa_examples: [
        {
          question: "How many years of experience does X have?",
          answer: "X has 10 years of experience",
        },
      ],
    });
    render(<DefineEntityTypeSlideOver open onClose={vi.fn()} editTarget={target} />, {
      wrapper: createWrapper(),
    });

    const question = screen.getByLabelText("Question 1") as HTMLInputElement;
    const answer = screen.getByLabelText("Answer 1") as HTMLInputElement;
    expect(question.value).toBe("How many years of experience does X have?");
    expect(answer.value).toBe("X has 10 years of experience");
    expect(screen.queryByLabelText("Question 2")).toBeNull();
  });

  // Spec Alignment row 20
  it("submits_added_qa_pair", async () => {
    render(
      <DefineEntityTypeSlideOver
        open
        onClose={vi.fn()}
        editTarget={entityType({ qa_examples: [] })}
      />,
      { wrapper: createWrapper() },
    );

    fireEvent.click(screen.getByRole("button", { name: "+ Add Q&A pair" }));
    fireEvent.change(screen.getByLabelText("Question 1"), {
      target: { value: "What is the candidate's tenure?" },
    });
    fireEvent.change(screen.getByLabelText("Answer 1"), {
      target: { value: "Five years at Acme" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    const [url, init] = mockFetch.mock.calls.at(-1)!;
    expect(url).toContain("/entity-types/years_experience");
    expect(init.method).toBe("PUT");
    expect(lastRequestBody().qa_examples).toEqual([
      { question: "What is the candidate's tenure?", answer: "Five years at Acme" },
    ]);
  });

  // Spec Alignment row 21
  it("removes_qa_pair_row", async () => {
    const target = entityType({
      qa_examples: [
        { question: "First question", answer: "First answer" },
        { question: "Second question", answer: "Second answer" },
      ],
    });
    render(<DefineEntityTypeSlideOver open onClose={vi.fn()} editTarget={target} />, {
      wrapper: createWrapper(),
    });

    fireEvent.click(screen.getByRole("button", { name: "Remove Q&A pair 1" }));
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    expect(lastRequestBody().qa_examples).toEqual([
      { question: "Second question", answer: "Second answer" },
    ]);
  });

  // Spec Alignment row 22
  it("blocks_partial_qa_row", async () => {
    const onClose = vi.fn();
    render(
      <DefineEntityTypeSlideOver
        open
        onClose={onClose}
        editTarget={entityType({ qa_examples: [] })}
      />,
      { wrapper: createWrapper() },
    );

    fireEvent.click(screen.getByRole("button", { name: "+ Add Q&A pair" }));
    fireEvent.change(screen.getByLabelText("Question 1"), {
      target: { value: "A question with no answer" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("alert")).toBeDefined();
    expect(mockFetch).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
    // The slide-over stays open with the typed text intact.
    expect((screen.getByLabelText("Question 1") as HTMLInputElement).value).toBe(
      "A question with no answer",
    );
  });

  // Spec Alignment row 23
  it("submits_empty_qa_examples", async () => {
    const onClose = vi.fn();
    mockFetch.mockResolvedValue(okResponse(201));
    render(<DefineEntityTypeSlideOver open onClose={onClose} editTarget={null} />, {
      wrapper: createWrapper(),
    });

    fireEvent.change(screen.getByPlaceholderText("vendor_name"), {
      target: { value: "vendor_name" },
    });
    fireEvent.change(screen.getByPlaceholderText("Name of a vendor / supplier"), {
      target: { value: "Name of a vendor" },
    });
    fireEvent.change(screen.getByPlaceholderText("Acme Supplies, Global Tech Ltd"), {
      target: { value: "Acme Supplies, Global Tech Ltd" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create entity type" }));

    await waitFor(() => expect(mockFetch).toHaveBeenCalled());
    const body = lastRequestBody();
    expect(body.qa_examples).toEqual([]);
    await waitFor(() => expect(onClose).toHaveBeenCalled());
  });
});
