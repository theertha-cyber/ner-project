import { ReactNode } from "react";
import { DataPlaneGate } from "@/components/data-plane/data-plane-gate";

export default function AnalyticsLayout({ children }: { children: ReactNode }) {
  return <DataPlaneGate>{children}</DataPlaneGate>;
}
