export interface JobProgressProps {
  currentEpoch: number | null;
  currentLoss: number | null;
  numEpochs: number;
}

export function JobProgress({ currentEpoch, currentLoss, numEpochs }: JobProgressProps) {
  if (currentEpoch === null) return null;

  const pct = Math.min(Math.max((currentEpoch / numEpochs) * 100, 0), 100);

  return (
    <div className="space-y-2">
      <h4 className="text-sm font-medium text-gray-700">Training Progress</h4>
      <div className="flex items-center justify-between text-xs text-gray-600">
        <span>
          Epoch {currentEpoch} / {numEpochs}
        </span>
        {currentLoss !== null && (
          <span>Loss: {currentLoss.toFixed(4)}</span>
        )}
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-gray-200">
        <div
          className="h-full rounded-full bg-status-running transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
