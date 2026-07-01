"use client";

export type BadgeVariant =
  | "active"
  | "inactive"
  | "running"
  | "completed"
  | "failed"
  | "pending_approval"
  | "queued"
  | "rejected"
  | "cancelled"
  | "promoted"
  | "training"
  | "archived";

const variantClasses: Record<BadgeVariant, string> = {
  active: "bg-status-active text-white",
  inactive: "bg-status-inactive text-white",
  running: "bg-status-running text-white",
  completed: "bg-status-completed text-white",
  failed: "bg-status-failed text-white",
  pending_approval: "bg-status-pending_approval text-white",
  queued: "bg-status-queued text-white",
  rejected: "bg-status-rejected text-white",
  cancelled: "bg-status-cancelled text-white",
  promoted: "bg-status-promoted text-white",
  training: "bg-status-training text-white",
  archived: "bg-status-archived text-white",
};

export interface BadgeProps {
  variant: BadgeVariant;
  label?: string;
}

export function Badge({ variant, label }: BadgeProps) {
  const text = label ?? variant.replace(/_/g, " ");
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${variantClasses[variant]}`}
    >
      {text}
    </span>
  );
}
