import { describe, it, expect } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useLayoutPreference } from "./use-layout-preference";

describe("useLayoutPreference", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("defaults to editorial", () => {
    const { result } = renderHook(() => useLayoutPreference());
    expect(result.current[0]).toBe("editorial");
  });

  it("persists command to localStorage", () => {
    const { result } = renderHook(() => useLayoutPreference());
    act(() => result.current[1]("command"));
    expect(result.current[0]).toBe("command");
    expect(localStorage.getItem("portal-layout")).toBe("command");
  });

  it("reads stored value from localStorage", () => {
    localStorage.setItem("portal-layout", "command");
    const { result } = renderHook(() => useLayoutPreference());
    expect(result.current[0]).toBe("command");
  });
});
