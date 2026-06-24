import type { TimelineStep } from "@/types/training-jobs";

export interface JobTimelineProps {
  steps: TimelineStep[];
}

const DOT_CLASS: Record<string, string> = {
  completed: "bg-status-completed",
  active: "bg-status-running ring-2 ring-status-running/30",
  pending: "bg-gray-300",
};

const LINE_CLASS: Record<string, string> = {
  completed: "bg-status-completed",
  active: "bg-status-running",
  pending: "bg-gray-200",
};

export function JobTimeline({ steps }: JobTimelineProps) {
  return (
    <div className="space-y-0">
      {steps.map((step, i) => {
        const isLast = i === steps.length - 1;
        return (
          <div key={step.label} className="relative flex gap-3">
            <div className="flex flex-col items-center">
              <div
                className={`h-3 w-3 rounded-full ${DOT_CLASS[step.state]}`}
              />
              {!isLast && (
                <div
                  className={`mt-0.5 w-0.5 flex-1 ${LINE_CLASS[step.state]}`}
                  style={{ minHeight: "1.25rem" }}
                />
              )}
            </div>
            <div className="pb-2 text-sm">
              <span
                className={
                  step.state === "active"
                    ? "font-semibold text-gray-900"
                    : step.state === "completed"
                      ? "text-gray-600"
                      : "text-gray-400"
                }
              >
                {step.label}
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
