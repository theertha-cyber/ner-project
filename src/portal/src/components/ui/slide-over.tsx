"use client";

import { useEffect, useState, ReactNode } from "react";
import { createPortal } from "react-dom";
import { useFocusTrap } from "@/hooks/use-focus-trap";

export interface SlideOverProps {
  open: boolean;
  onClose: () => void;
  width?: number;
  children: ReactNode;
}

export function SlideOver({ open, onClose, width = 480, children }: SlideOverProps) {
  const { panelRef } = useFocusTrap({ open, onClose });
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) return null;

  return createPortal(
    <>
      {/* Backdrop */}
      <div
        className={[
          "fixed inset-0 z-40 bg-black/40 transition-opacity",
          open ? "opacity-100" : "pointer-events-none opacity-0",
        ].join(" ")}
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        className={[
          "fixed inset-y-0 right-0 z-50 flex flex-col bg-surface-overlay shadow-overlay transition-transform duration-300",
          open ? "translate-x-0" : "translate-x-full",
        ].join(" ")}
        style={{ width }}
      >
        {children}
      </div>
    </>,
    document.body,
  );
}
