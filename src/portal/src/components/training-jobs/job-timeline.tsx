import type { JobStatus, TimelineStep } from "@/types/training-jobs";
import { badgeDotClass } from "@/components/ui";

export interface JobTimelineProps {
  steps: TimelineStep[];
  currentStatus: JobStatus;
}

export function JobTimeline({ steps, currentStatus }: JobTimelineProps) {
  return (
    <div className="flex items-center" role="list" aria-label="Job status timeline">
      {steps.map((step, i) => {
        const isLast = i === steps.length - 1;
        const dotClass =
          step.state === "active"
            ? badgeDotClass(currentStatus)
            : step.state === "completed"
              ? badgeDotClass("completed")
              : null;

        return (
          <div key={step.label} role="listitem" className="flex flex-1 items-center last:flex-none">
            <div className="flex flex-col items-center gap-1">
              <div
                data-testid="timeline-dot"
                data-state={step.state}
                className={dotClass ? `h-3 w-3 rounded-full ${dotClass}` : "h-3 w-3 rounded-full"}
                style={
                  dotClass
                    ? undefined
                    : { background: "var(--surface-3)", border: "1px solid var(--line)" }
                }
              />
              <span
                className={`whitespace-nowrap font-body text-xs ${step.state === "active" ? "font-bold" : ""}`}
                style={{
                  color:
                    step.state === "pending" ? "var(--ink-3)" : "var(--ink)",
                }}
              >
                {step.label}
              </span>
            </div>
            {!isLast && (
              <div
                data-testid="timeline-connector"
                data-completed={step.state === "completed"}
                className={step.state === "completed" ? `mx-1 ${badgeDotClass("completed")}` : "mx-1"}
                style={{
                  flex: 1,
                  height: 2,
                  background: step.state === "completed" ? undefined : "var(--line)",
                }}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}
