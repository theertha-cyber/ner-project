"use client";

export interface FilterSelectOption<T extends string> {
  value: T;
  label: string;
}

export interface FilterSelectProps<T extends string> {
  value: T;
  onChange: (value: T) => void;
  options: FilterSelectOption<T>[];
  ariaLabel: string;
}

export function FilterSelect<T extends string>({ value, onChange, options, ariaLabel }: FilterSelectProps<T>) {
  return (
    <div className="relative">
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2"
        style={{ color: "var(--ink-3)" }}
      >
        <path fillRule="evenodd" d="M2.628 1.601C5.028 1.206 7.49 1 10 1s4.973.206 7.372.601a.75.75 0 01.628.74v2.288a2.25 2.25 0 01-.659 1.59l-4.682 4.683a2.25 2.25 0 00-.659 1.59v3.037c0 .684-.31 1.33-.844 1.757l-1.937 1.55A.75.75 0 018 18.25v-5.757a2.25 2.25 0 00-.659-1.591L2.659 6.22A2.25 2.25 0 012 4.629V2.34a.75.75 0 01.628-.74z" clipRule="evenodd" />
      </svg>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T)}
        aria-label={ariaLabel}
        className="appearance-none rounded-md border py-1.5 pl-8 pr-8 text-sm font-medium outline-none"
        style={{ borderColor: "var(--line)", background: "var(--surface-3)", color: "var(--ink)" }}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 20 20"
        fill="currentColor"
        className="pointer-events-none absolute right-2.5 top-1/2 size-4 -translate-y-1/2"
        style={{ color: "var(--ink-3)" }}
        aria-hidden="true"
      >
        <path fillRule="evenodd" d="M5.22 8.22a.75.75 0 011.06 0L10 11.94l3.72-3.72a.75.75 0 111.06 1.06l-4.25 4.25a.75.75 0 01-1.06 0L5.22 9.28a.75.75 0 010-1.06z" clipRule="evenodd" />
      </svg>
    </div>
  );
}
