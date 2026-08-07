export interface StatItem {
  label: string;
  value: string | null;
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
  icon?: string;
  time?: string;
  id?: string;
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

export interface ActiveModelInfo {
  name: string;
  status: string;
  version: string;
  deployedAt: string;
}

/**
 * "resume" — task in progress; "start" — assigned but not begun;
 * "review" — already submitted, offered only when nothing else remains.
 */
export type ContinueWorkMode = "resume" | "start" | "review";

export interface ContinueWork {
  taskId: string;
  documentId: string;
  documentName: string;
  status: string;
  spanCount: number;
  mode: ContinueWorkMode;
}

export type ResponseQualityStatus = "healthy" | "monitor" | "needs_attention" | "no_data";

export interface ResponseQuality {
  status: ResponseQualityStatus;
  satisfactionPct: number | null;
  positive: number;
  negative: number;
  rated: number;
  total: number;
  recommendation: string;
}

export interface DashboardData {
  kicker: string;
  title: string;
  line: string;
  stats: StatItem[];
  pTitle: string;
  pMeta: string;
  pRows: ActivityRow[];
  sideTop: string;
  sideMeta: string;
  big: string;
  bigUnit: string;
  bar: number;
  sideMetrics: [SideMetric, SideMetric, SideMetric];
  sideBot: string;
  sideRows: SideRow[];
  responseQuality?: ResponseQuality | null;
  activeModel?: ActiveModelInfo | null;
  continueWork?: ContinueWork | null;
}

export interface DashboardSummaryResponse {
  data: DashboardData;
  sources: Record<"tenants" | "training" | "documents" | "annotations" | "models" | "feedback", boolean>;
}

export interface DashboardActivityResponse {
  rows: ActivityRow[];
}
