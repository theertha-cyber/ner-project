import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PlaygroundTab } from "./PlaygroundTab";

const mockAuthFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({
  authFetch: (...args: unknown[]) => mockAuthFetch(...args),
}));

const mockUseModelVersions = vi.fn();
vi.mock("@/hooks/use-model-versions", () => ({
  useModelVersions: () => mockUseModelVersions(),
}));

function makeExtractResponse(entities: object[], modelVersion = "1") {
  return new Response(
    JSON.stringify({ entities, model_version: modelVersion }),
    { status: 200 }
  );
}

describe("PlaygroundTab", () => {
  beforeEach(() => {
    mockAuthFetch.mockReset();
    mockUseModelVersions.mockReturnValue({ activeModel: { version_number: 3 } });
  });

  it("calls POST /api/v1/extract, disables button during request, renders grouped entities on 200", async () => {
    const entities = [
      { entity_type: "B-ORG", value: "Acme", confidence: 0.99, start_offset: 0, end_offset: 4 },
    ];
    let resolveRequest: (value: Response) => void;
    const pendingRequest = new Promise<Response>((res) => { resolveRequest = res; });
    mockAuthFetch.mockReturnValue(pendingRequest);

    render(<PlaygroundTab />);

    const button = screen.getByRole("button", { name: /run extraction/i });
    fireEvent.click(button);

    await waitFor(() => expect(button.hasAttribute("disabled")).toBe(true));

    expect(mockAuthFetch).toHaveBeenCalledWith(
      "/api/v1/extract",
      expect.objectContaining({ method: "POST" })
    );

    resolveRequest!(makeExtractResponse(entities));

    await waitFor(() => expect(screen.getByText("Acme")).toBeDefined());
    expect(screen.getByText("ORG")).toBeDefined();
    expect(screen.getByText("1 entities · 1 types")).toBeDefined();
    expect(button.hasAttribute("disabled")).toBe(false);
  });

  it("merges multi-token entities with average confidence", async () => {
    const entities = [
      { entity_type: "B-PER", value: "Steve", confidence: 0.98, start_offset: 0, end_offset: 5 },
      { entity_type: "I-PER", value: "Jobs", confidence: 0.97, start_offset: 6, end_offset: 10 },
    ];
    mockAuthFetch.mockResolvedValue(makeExtractResponse(entities));

    render(<PlaygroundTab />);
    fireEvent.click(screen.getByRole("button", { name: /run extraction/i }));

    await waitFor(() => expect(screen.getByText("Steve Jobs")).toBeDefined());
    expect(screen.getByText("0.975")).toBeDefined();
    expect(screen.getByText("PER")).toBeDefined();
  });

  it("renders groups in alphabetical order", async () => {
    const entities = [
      { entity_type: "B-PER", value: "Alice", confidence: 0.95, start_offset: 0, end_offset: 5 },
      { entity_type: "B-ORG", value: "Acme", confidence: 0.99, start_offset: 10, end_offset: 14 },
      { entity_type: "B-LOC", value: "Paris", confidence: 0.90, start_offset: 20, end_offset: 25 },
    ];
    mockAuthFetch.mockResolvedValue(makeExtractResponse(entities));

    render(<PlaygroundTab />);
    fireEvent.click(screen.getByRole("button", { name: /run extraction/i }));

    await waitFor(() => expect(screen.getByText("Alice")).toBeDefined());

    const headings = screen.getAllByText(/^(LOC|ORG|PER)$/);
    expect(headings[0].textContent).toBe("LOC");
    expect(headings[1].textContent).toBe("ORG");
    expect(headings[2].textContent).toBe("PER");
  });

  it("orders entities within a group by start_offset", async () => {
    const entities = [
      { entity_type: "B-ORG", value: "ZCorp", confidence: 0.90, start_offset: 20, end_offset: 25 },
      { entity_type: "B-ORG", value: "Acme", confidence: 0.99, start_offset: 0, end_offset: 4 },
    ];
    mockAuthFetch.mockResolvedValue(makeExtractResponse(entities));

    render(<PlaygroundTab />);
    fireEvent.click(screen.getByRole("button", { name: /run extraction/i }));

    await waitFor(() => {
      const items = screen.getAllByText(/^(ZCorp|Acme)$/);
      expect(items[0].textContent).toBe("Acme");
      expect(items[1].textContent).toBe("ZCorp");
    });
  });

  it("shows spinner in results panel during in-flight; no previous results shown", async () => {
    const entities = [
      { entity_type: "B-PER", value: "Alice", confidence: 0.95, start_offset: 0, end_offset: 5 },
    ];
    let resolveRequest: (value: Response) => void;
    const pendingRequest = new Promise<Response>((res) => { resolveRequest = res; });
    mockAuthFetch.mockReturnValue(pendingRequest);

    render(<PlaygroundTab />);

    fireEvent.click(screen.getByRole("button", { name: /run extraction/i }));

    await waitFor(() => {
      const spinners = screen.queryAllByRole("status");
      expect(spinners.length).toBeGreaterThan(0);
    });
    expect(screen.queryByText("Alice")).toBeNull();

    resolveRequest!(makeExtractResponse(entities));
    await waitFor(() => expect(screen.getByText("Alice")).toBeDefined());
  });

  it("updates model version label from response", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeExtractResponse([], "3"));
    render(<PlaygroundTab />);

    fireEvent.click(screen.getByRole("button", { name: /run extraction/i }));

    await waitFor(() => expect(screen.getByText("v3 · serving")).toBeDefined());
  });

  it("prevents API call when textarea is empty", async () => {
    render(<PlaygroundTab />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "   " } });

    const button = screen.getByRole("button", { name: /run extraction/i });
    fireEvent.click(button);

    expect(mockAuthFetch).not.toHaveBeenCalled();
  });

  it("shows entity count and type count summary", async () => {
    const entities = [
      { entity_type: "B-PER", value: "Alice", confidence: 0.95, start_offset: 0, end_offset: 5 },
      { entity_type: "B-ORG", value: "Acme", confidence: 0.99, start_offset: 10, end_offset: 14 },
    ];
    mockAuthFetch.mockResolvedValue(makeExtractResponse(entities));

    render(<PlaygroundTab />);
    fireEvent.click(screen.getByRole("button", { name: /run extraction/i }));

    await waitFor(() => expect(screen.getByText("2 entities · 2 types")).toBeDefined());
  });

  it("does not show a confirmation dialog when a fine-tuned model is active", () => {
    mockUseModelVersions.mockReturnValue({ activeModel: { version_number: 3 } });
    mockAuthFetch.mockResolvedValue(makeExtractResponse([]));
    render(<PlaygroundTab />);

    fireEvent.click(screen.getByRole("button", { name: /run extraction/i }));

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(mockAuthFetch).toHaveBeenCalled();
  });

  it("shows a confirmation dialog when only the base model is available", () => {
    mockUseModelVersions.mockReturnValue({ activeModel: { version_number: 0 } });
    render(<PlaygroundTab />);

    fireEvent.click(screen.getByRole("button", { name: /run extraction/i }));

    expect(screen.getByRole("dialog")).toBeDefined();
    expect(mockAuthFetch).not.toHaveBeenCalled();
  });

  it("confirming the dialog proceeds with the extraction", async () => {
    mockUseModelVersions.mockReturnValue({ activeModel: { version_number: 0 } });
    mockAuthFetch.mockResolvedValue(makeExtractResponse([]));
    render(<PlaygroundTab />);

    fireEvent.click(screen.getByRole("button", { name: /run extraction/i }));
    fireEvent.click(screen.getByRole("button", { name: /use base model/i }));

    await waitFor(() => expect(mockAuthFetch).toHaveBeenCalled());
  });

  it("declining the dialog cancels the run", () => {
    mockUseModelVersions.mockReturnValue({ activeModel: { version_number: 0 } });
    render(<PlaygroundTab />);

    fireEvent.click(screen.getByRole("button", { name: /run extraction/i }));
    fireEvent.click(screen.getByRole("button", { name: /cancel/i }));

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(mockAuthFetch).not.toHaveBeenCalled();
  });
});
