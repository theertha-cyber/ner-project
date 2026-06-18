import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDarkMode } from "./use-dark-mode";

beforeEach(() => {
  localStorage.clear();
  document.documentElement.classList.remove("dark");
});

afterEach(() => {
  localStorage.clear();
  document.documentElement.classList.remove("dark");
  vi.restoreAllMocks();
});

describe("useDarkMode", () => {
  it("initialises from localStorage dark preference", () => {
    localStorage.setItem("portal-theme", "dark");
    const { result } = renderHook(() => useDarkMode());
    expect(result.current.dark).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("initialises to light when localStorage is absent", () => {
    const { result } = renderHook(() => useDarkMode());
    expect(result.current.dark).toBe(false);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("toggle flips dark state and adds dark class to documentElement", () => {
    const { result } = renderHook(() => useDarkMode());
    act(() => result.current.toggle());
    expect(result.current.dark).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });

  it("toggle persists preference to localStorage", () => {
    const { result } = renderHook(() => useDarkMode());
    act(() => result.current.toggle());
    expect(localStorage.getItem("portal-theme")).toBe("dark");
  });

  it("second toggle reverts to light, removes dark class, stores light", () => {
    localStorage.setItem("portal-theme", "dark");
    const { result } = renderHook(() => useDarkMode());
    act(() => result.current.toggle());
    expect(result.current.dark).toBe(false);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(localStorage.getItem("portal-theme")).toBe("light");
  });
});
