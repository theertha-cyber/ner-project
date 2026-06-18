"use client";

import { useState, useEffect } from "react";

type Layout = "editorial" | "command";
const STORAGE_KEY = "portal-layout";

export function useLayoutPreference(): [Layout, (l: Layout) => void] {
  const [layout, setLayoutState] = useState<Layout>("editorial");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "editorial" || stored === "command") {
      setLayoutState(stored);
    }
  }, []);

  function setLayout(next: Layout) {
    setLayoutState(next);
    if (typeof window !== "undefined") {
      localStorage.setItem(STORAGE_KEY, next);
    }
  }

  return [layout, setLayout];
}
