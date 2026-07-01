import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PlaygroundTab } from "./PlaygroundTab";

const mockAuthFetch = vi.fn();
vi.mock("@/lib/auth-fetch", () => ({
  authFetch: (...args: unknown[]) => mockAuthFetch(...args),
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
  });

  it("Test 3: calls POST /api/v1/extract, disables button during request, renders entity rows on 200", async () => {
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
    expect(screen.getByText("B-ORG")).toBeDefined();
    expect(button.hasAttribute("disabled")).toBe(false);
  });

  it("Test 4: spinner visible in results panel during in-flight; no previous results shown", async () => {
    const entities = [
      { entity_type: "B-PER", value: "Alice", confidence: 0.95, start_offset: 0, end_offset: 5 },
    ];
    let resolveRequest: (value: Response) => void;
    const pendingRequest = new Promise<Response>((res) => { resolveRequest = res; });
    mockAuthFetch.mockReturnValue(pendingRequest);

    render(<PlaygroundTab />);

    fireEvent.click(screen.getByRole("button", { name: /run extraction/i }));

    // Spinner should appear while request is pending
    await waitFor(() => {
      const spinners = screen.queryAllByRole("status");
      expect(spinners.length).toBeGreaterThan(0);
    });
    expect(screen.queryByText("Alice")).toBeNull();

    resolveRequest!(makeExtractResponse(entities));
    await waitFor(() => expect(screen.getByText("Alice")).toBeDefined());
  });

  it("Test 5: model version label updates from response", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeExtractResponse([], "3"));
    render(<PlaygroundTab />);

    fireEvent.click(screen.getByRole("button", { name: /run extraction/i }));

    await waitFor(() => expect(screen.getByText("model v3 · serving")).toBeDefined());
  });

  it("Test 6: no API call when textarea is empty", async () => {
    render(<PlaygroundTab />);
    const textarea = screen.getByRole("textbox");
    fireEvent.change(textarea, { target: { value: "   " } });

    const button = screen.getByRole("button", { name: /run extraction/i });
    fireEvent.click(button);

    expect(mockAuthFetch).not.toHaveBeenCalled();
  });
});
