import { describe, it, expect, vi, beforeEach } from "vitest";

describe("api constants", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("returns empty string when env var is absent", async () => {
    vi.stubEnv("NEXT_PUBLIC_DOCUMENT_URL", undefined as unknown as string);
    const { DOCUMENT_URL } = await import("./api");
    expect(DOCUMENT_URL).toBe("");
  });

  it("surfaces defined env var correctly", async () => {
    vi.stubEnv("NEXT_PUBLIC_GATEWAY_URL", "http://localhost:8000");
    const { GATEWAY_URL } = await import("./api");
    expect(GATEWAY_URL).toBe("http://localhost:8000");
  });
});
