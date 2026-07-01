import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "brand-primary": "var(--color-brand-primary)",
        "brand-hover": "var(--color-brand-hover)",
        surface: "var(--color-surface)",
        "surface-raised": "var(--color-surface-raised)",
        "surface-overlay": "var(--color-surface-overlay)",
        "text-primary": "var(--color-text-primary)",
        "text-secondary": "var(--color-text-secondary)",
        "text-disabled": "var(--color-text-disabled)",
        border: "var(--color-border)",
        "border-focus": "var(--color-border-focus)",
        "status-active": "var(--color-status-active)",
        "status-inactive": "var(--color-status-inactive)",
        "status-running": "var(--color-status-running)",
        "status-completed": "var(--color-status-completed)",
        "status-failed": "var(--color-status-failed)",
        "status-pending_approval": "var(--color-status-pending_approval)",
        "status-queued": "var(--color-status-queued)",
        "status-rejected": "var(--color-status-rejected)",
        "status-cancelled": "var(--color-status-cancelled)",
        "status-promoted": "var(--color-status-promoted)",
        "status-training": "var(--color-status-training)",
        "status-archived": "var(--color-status-archived)",
        success: "var(--color-success)",
        warning: "var(--color-warning)",
        error: "var(--color-error)",
        info: "var(--color-info)",
        "delta-up": "var(--color-delta-up)",
        "delta-warn": "var(--color-delta-warn)",
        "delta-neutral": "var(--color-delta-neutral)",
      },
      fontFamily: {
        display: ["var(--font-display)", "sans-serif"],
        body: ["var(--font-body)", "sans-serif"],
        mono: ["var(--font-mono)", "monospace"],
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
        full: "var(--radius-full)",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        overlay: "var(--shadow-overlay)",
      },
      animation: {
        "menu-pop": "ner-menu-pop .18s cubic-bezier(.16,1,.3,1) both",
        "fade-up": "ner-fade-up 0.35s ease both",
      },
    },
  },
  plugins: [],
};

export default config;
