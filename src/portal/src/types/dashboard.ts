export interface StatItem {
  label: string;
  value: number | null;
  unit: string;
  sub: string;
  delta: string;
  dir?: "up" | "warn";
}

export interface ActivityRow {
  tag: string;
  tk: string;
  title: string;
  sub: string;
  go: string;
}

export interface SideRow {
  label: string;
  val: string;
  pct: number;
  c: string;
}

export interface SideMetric {
  k: string;
  v: string;
}

export interface DashboardData {
  kicker: string;
  title: string;
  line: string;
  stats: [StatItem, StatItem, StatItem, StatItem];
  pTitle: string;
  pMeta: string;
  pRows: [ActivityRow, ActivityRow, ActivityRow, ActivityRow];
  sideTop: string;
  sideMeta: string;
  big: string;
  bigUnit: string;
  bar: number;
  sideMetrics: [SideMetric, SideMetric, SideMetric];
  sideBot: string;
  sideRows: SideRow[];
}

export interface DashboardSummaryResponse {
  data: DashboardData;
  sources: Record<"tenants" | "training" | "documents" | "annotations" | "models", boolean>;
}
