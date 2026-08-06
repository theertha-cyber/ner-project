"use client";

import { useState, useEffect } from "react";

const STORAGE_KEY = "portal-theme";
const listeners = new Set<(dark: boolean) => void>();

function notify(dark: boolean) {
  listeners.forEach((listener) => listener(dark));
}

export interface UseDarkModeReturn {
  dark: boolean;
  toggle: () => void;
}

export function useDarkMode(): UseDarkModeReturn {
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    const isDark = stored === "dark";
    setDark(isDark);
    if (isDark) {
      document.documentElement.classList.add("dark");
    } else {
      document.documentElement.classList.remove("dark");
    }

    listeners.add(setDark);
    return () => {
      listeners.delete(setDark);
    };
  }, []);

  function toggle() {
    const next = !dark;
    if (next) {
      document.documentElement.classList.add("dark");
      localStorage.setItem(STORAGE_KEY, "dark");
    } else {
      document.documentElement.classList.remove("dark");
      localStorage.setItem(STORAGE_KEY, "light");
    }
    notify(next);
  }

  return { dark, toggle };
}
