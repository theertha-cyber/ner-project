"use client";

import { useState, useEffect } from "react";

const STORAGE_KEY = "portal-theme";

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
  }, []);

  function toggle() {
    setDark((prev) => {
      const next = !prev;
      if (next) {
        document.documentElement.classList.add("dark");
        localStorage.setItem(STORAGE_KEY, "dark");
      } else {
        document.documentElement.classList.remove("dark");
        localStorage.setItem(STORAGE_KEY, "light");
      }
      return next;
    });
  }

  return { dark, toggle };
}
