import type { TrainingJob } from "@/types/training-jobs";
import { JobCard } from "./job-card";
import { Spinner } from "@/components/ui";

export interface JobListProps {
  jobs: TrainingJob[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  isLoading: boolean;
}

export function JobList({ jobs, selectedId, onSelect, isLoading }: JobListProps) {
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Spinner />
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <p className="py-12 text-center text-sm text-gray-500">
        No training jobs found.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {jobs.map((job) => (
        <JobCard
          key={job.id}
          job={job}
          isSelected={job.id === selectedId}
          onClick={() => onSelect(job.id)}
        />
      ))}
    </div>
  );
}
