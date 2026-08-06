"use client";

import { useEffect, useRef, useState } from "react";

export interface ComboboxOption {
  value: string;
  label: string;
}

export interface SearchableComboboxProps {
  value: string;
  onChange: (value: string) => void;
  options: ComboboxOption[];
  ariaLabel: string;
  placeholder?: string;
}

export function SearchableCombobox({ value, onChange, options, ariaLabel, placeholder }: SearchableComboboxProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  const selectedLabel = options.find((opt) => opt.value === value)?.label ?? "";
  const filtered = query.trim()
    ? options.filter((opt) => opt.label.toLowerCase().includes(query.trim().toLowerCase()))
    : options;

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  function selectOption(opt: ComboboxOption) {
    onChange(opt.value);
    setOpen(false);
    setQuery("");
  }

  return (
    <div ref={containerRef} className="relative" style={{ minWidth: 200 }}>
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2"
        style={{ color: "var(--ink-3)" }}
      >
        <path
          fillRule="evenodd"
          d="M9 3.5a5.5 5.5 0 100 11 5.5 5.5 0 000-11zM2 9a7 7 0 1112.452 4.391l3.328 3.329a.75.75 0 11-1.06 1.06l-3.329-3.328A7 7 0 012 9z"
          clipRule="evenodd"
        />
      </svg>
      <input
        type="text"
        role="combobox"
        aria-label={ariaLabel}
        aria-expanded={open}
        placeholder={placeholder}
        value={open ? query : selectedLabel}
        onFocus={() => setOpen(true)}
        onClick={() => setOpen(true)}
        onChange={(e) => {
          setQuery(e.target.value);
          setOpen(true);
        }}
        className="rounded-md border py-1.5 pl-8 pr-8 text-sm font-medium outline-none w-full"
        style={{ borderColor: "var(--line)", background: "var(--surface-3)", color: "var(--ink)" }}
      />
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        className="pointer-events-none absolute right-2.5 top-1/2 size-4 -translate-y-1/2"
        style={{ color: "var(--ink-3)" }}
        aria-hidden="true"
      >
        <path
          fillRule="evenodd"
          d="M5.22 8.22a.75.75 0 011.06 0L10 11.94l3.72-3.72a.75.75 0 111.06 1.06l-4.25 4.25a.75.75 0 01-1.06 0L5.22 9.28a.75.75 0 010-1.06z"
          clipRule="evenodd"
        />
      </svg>
      {open && (
        <ul
          role="listbox"
          className="absolute z-10 mt-1 max-h-64 w-full overflow-auto rounded-md border text-sm"
          style={{ borderColor: "var(--line)", background: "var(--surface-3)", color: "var(--ink)" }}
        >
          {filtered.length === 0 && (
            <li className="px-3 py-2" style={{ color: "var(--ink-3)" }}>
              No matches
            </li>
          )}
          {filtered.map((opt) => (
            <li
              key={opt.value}
              role="option"
              aria-selected={opt.value === value}
              onMouseDown={(e) => {
                e.preventDefault();
                selectOption(opt);
              }}
              className="cursor-pointer px-3 py-2 hover:opacity-80"
              style={{
                fontWeight: opt.value === value ? 700 : 400,
                background: opt.value === value ? "var(--line)" : "transparent",
              }}
            >
              {opt.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
