"use client";

import { useId } from "react";

import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export interface ChartSeries {
  name: string;
  data: number[];
}

export interface ChartPayload {
  chart_type: "bar" | "line" | "pie";
  title: string;
  x_label?: string | null;
  y_label?: string | null;
  categories: string[];
  series: ChartSeries[];
}

// Fixed order, never cycled — colour follows the entity, not its rank. Past the
// eighth slot the tail folds into "Other" rather than inventing a ninth hue.
const SERIES_TOKENS = [
  "var(--chart-series-1)",
  "var(--chart-series-2)",
  "var(--chart-series-3)",
  "var(--chart-series-4)",
  "var(--chart-series-5)",
  "var(--chart-series-6)",
  "var(--chart-series-7)",
  "var(--chart-series-8)",
];
const MAX_SLICES = SERIES_TOKENS.length;

/** Vertical fade built from the slot's own token, so the gradient follows the theme
 * without a second set of colours to keep in step. Ends at 0.45 rather than 0 — a mark
 * that fades to nothing loses its baseline, and the bar's height is the datum. */
function SeriesGradients({ prefix }: { prefix: string }) {
  return (
    <defs>
      {SERIES_TOKENS.map((token, index) => (
        <linearGradient key={index} id={`${prefix}-${index}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={token} stopOpacity={0.95} />
          <stop offset="100%" stopColor={token} stopOpacity={0.45} />
        </linearGradient>
      ))}
    </defs>
  );
}

const AXIS_STYLE = { fill: "var(--color-text-secondary)", fontSize: 12 };
const TOOLTIP_STYLE = {
  background: "var(--color-surface-overlay)",
  border: "1px solid var(--color-border)",
  borderRadius: 8,
  color: "var(--color-text-primary)",
  fontSize: 12,
};

function isRenderable(chart: ChartPayload | null | undefined): chart is ChartPayload {
  if (!chart) return false;
  if (!["bar", "line", "pie"].includes(chart.chart_type)) return false;
  if (!Array.isArray(chart.categories) || chart.categories.length === 0) return false;
  if (!Array.isArray(chart.series) || chart.series.length === 0) return false;
  return chart.series.every(
    (s) => Array.isArray(s.data) && s.data.length === chart.categories.length,
  );
}

/** Recharts wants one row per category with a key per series. */
function toRows(chart: ChartPayload): Record<string, string | number>[] {
  return chart.categories.map((category, index) => {
    const row: Record<string, string | number> = { category };
    chart.series.forEach((series) => {
      row[series.name] = series.data[index];
    });
    return row;
  });
}

/** A pie shows one series as parts of a whole; the tail folds into a single slice. */
function toSlices(chart: ChartPayload): { name: string; value: number }[] {
  const values = chart.series[0].data;
  const slices = chart.categories.map((name, index) => ({ name, value: values[index] }));
  if (slices.length <= MAX_SLICES) return slices;

  const head = slices.slice(0, MAX_SLICES - 1);
  const tail = slices.slice(MAX_SLICES - 1);
  return [...head, { name: "Other", value: tail.reduce((sum, s) => sum + s.value, 0) }];
}

export function ChartRenderer({ chart }: { chart: ChartPayload | null | undefined }) {
  const instanceId = useId();
  // A payload the UI cannot draw is skipped in silence: the answer text and its
  // citations are still correct, and a rendering complaint would tell the reader
  // nothing they can act on.
  if (!isRenderable(chart)) return null;

  const rows = toRows(chart);
  const multiSeries = chart.series.length > 1;
  // Gradient ids are document-global, so namespace them per instance — two charts in one
  // thread would otherwise share (and fight over) the same defs.
  const gradientPrefix = `chart-grad-${instanceId.replace(/:/g, "")}`;
  const gradientFill = (index: number) => `url(#${gradientPrefix}-${index % MAX_SLICES})`;
  // Marks are drawn immediately (isAnimationActive={false} below): the chart lives in
  // a message thread that re-renders as tokens arrive, and an entry animation would
  // replay from zero on every one of those renders.

  return (
    <figure
      className="chart-figure"
      style={{ margin: "12px 0 0", width: "100%" }}
      aria-label={chart.title}
    >
      <figcaption
        style={{
          color: "var(--color-text-primary)",
          fontSize: 13,
          fontWeight: 600,
          marginBottom: 8,
        }}
      >
        {chart.title}
      </figcaption>

      <ResponsiveContainer width="100%" height={240}>
        {chart.chart_type === "pie" ? (
          <PieChart>
            <SeriesGradients prefix={gradientPrefix} />
            <Pie
              data={toSlices(chart)}
              dataKey="value"
              nameKey="name"
              outerRadius="78%"
              // A 2px surface ring separates adjacent slices.
              stroke="var(--color-surface)"
              strokeWidth={2}
              label={({ name }) => name}
              isAnimationActive={false}
            >
              {toSlices(chart).map((slice, index) => (
                <Cell key={slice.name} fill={gradientFill(index)} />
              ))}
            </Pie>
            <Tooltip contentStyle={TOOLTIP_STYLE} />
            <Legend wrapperStyle={{ fontSize: 12, color: "var(--color-text-secondary)" }} />
          </PieChart>
        ) : chart.chart_type === "line" ? (
          <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
            <SeriesGradients prefix={gradientPrefix} />
            <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="category"
              tick={AXIS_STYLE}
              stroke="var(--color-border)"
              label={xAxisLabel(chart)}
            />
            <YAxis tick={AXIS_STYLE} stroke="var(--color-border)" label={yAxisLabel(chart)} />
            <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ stroke: "var(--color-border)" }} />
            {multiSeries && (
              <Legend wrapperStyle={{ fontSize: 12, color: "var(--color-text-secondary)" }} />
            )}
            {chart.series.map((series, index) => (
              <Line
                key={series.name}
                type="monotone"
                dataKey={series.name}
                stroke={SERIES_TOKENS[index % MAX_SLICES]}
                strokeWidth={2}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
                isAnimationActive={false}
              />
            ))}
          </LineChart>
        ) : (
          <BarChart data={rows} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
            <SeriesGradients prefix={gradientPrefix} />
            <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="category"
              tick={AXIS_STYLE}
              stroke="var(--color-border)"
              label={xAxisLabel(chart)}
            />
            <YAxis tick={AXIS_STYLE} stroke="var(--color-border)" label={yAxisLabel(chart)} />
            <Tooltip contentStyle={TOOLTIP_STYLE} cursor={{ fill: "var(--color-border)" }} />
            {multiSeries && (
              <Legend wrapperStyle={{ fontSize: 12, color: "var(--color-text-secondary)" }} />
            )}
            {chart.series.map((series, index) => (
              <Bar
                key={series.name}
                dataKey={series.name}
                fill={gradientFill(index)}
                radius={[4, 4, 0, 0]}
                isAnimationActive={false}
              />
            ))}
          </BarChart>
        )}
      </ResponsiveContainer>
    </figure>
  );
}

// Recharts draws an axis label with its own default grey unless `fill` is given as a
// prop — a `style.fill` is ignored for the attribute, so the label would ship a
// hardcoded colour that never follows the theme.
const LABEL_FILL = { fill: "var(--color-text-secondary)", fontSize: 12 };

function xAxisLabel(chart: ChartPayload) {
  return chart.x_label
    ? { value: chart.x_label, position: "insideBottom" as const, offset: -2, ...LABEL_FILL }
    : undefined;
}

function yAxisLabel(chart: ChartPayload) {
  return chart.y_label
    ? { value: chart.y_label, angle: -90, position: "insideLeft" as const, ...LABEL_FILL }
    : undefined;
}
