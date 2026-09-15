import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ChartRenderer, type ChartPayload } from "./ChartRenderer";

// Recharts' ResponsiveContainer measures its parent, and jsdom reports 0x0, so
// nothing would draw. Standing in a fixed-size container lets the real chart
// components render while leaving every colour and label assertion honest.
vi.mock("recharts", async () => {
  const actual = await vi.importActual<typeof import("recharts")>("recharts");
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
      <actual.ResponsiveContainer width={640} height={240}>
        {children as React.ReactElement}
      </actual.ResponsiveContainer>
    ),
  };
});

const BAR: ChartPayload = {
  chart_type: "bar",
  title: "Billed per quarter",
  x_label: "Quarter",
  y_label: "Amount",
  categories: ["Q1", "Q2", "Q3", "Q4"],
  series: [{ name: "amount", data: [120000, 95000, 143000, 160000] }],
};

function svgOf(container: HTMLElement) {
  return container.querySelector("svg");
}

describe("ChartRenderer", () => {
  it("renders a bar chart with its title and every category label (row 38)", () => {
    const { container } = render(<ChartRenderer chart={BAR} />);

    expect(screen.getByText("Billed per quarter")).toBeInTheDocument();
    for (const quarter of BAR.categories) {
      expect(screen.getByText(quarter)).toBeInTheDocument();
    }
    expect(container.querySelectorAll(".recharts-bar-rectangle").length).toBe(4);
  });

  it("renders line and pie payloads as their respective chart (row 39)", () => {
    const line = render(<ChartRenderer chart={{ ...BAR, chart_type: "line" }} />);
    expect(line.container.querySelector(".recharts-line")).toBeTruthy();
    expect(line.container.querySelector(".recharts-bar")).toBeFalsy();

    const pie = render(<ChartRenderer chart={{ ...BAR, chart_type: "pie" }} />);
    expect(pie.container.querySelector(".recharts-pie")).toBeTruthy();
    expect(pie.container.querySelector(".recharts-bar")).toBeFalsy();
  });

  it("colours marks from design tokens, never hardcoded hex (row 40)", () => {
    const { container } = render(<ChartRenderer chart={BAR} />);
    const svg = svgOf(container);

    const fills = Array.from(svg!.querySelectorAll("[fill]"))
      .map((el) => el.getAttribute("fill") ?? "")
      .filter((fill) => fill && fill !== "none");

    expect(fills.length).toBeGreaterThan(0);
    // A hex literal here would freeze the chart to one theme.
    expect(fills.some((fill) => /^#[0-9a-f]{3,8}$/i.test(fill))).toBe(false);

    // Marks are painted through a gradient, whose stops carry the tokens.
    const stops = Array.from(svg!.querySelectorAll("linearGradient stop")).map((stop) =>
      stop.getAttribute("stop-color"),
    );
    expect(stops.some((c) => c === "var(--chart-series-1)")).toBe(true);
    expect(stops.every((c) => c?.startsWith("var(--chart-series-"))).toBe(true);
  });

  it("builds each gradient from a single token so it follows the theme (row 39)", () => {
    const { container } = render(<ChartRenderer chart={BAR} />);
    const first = container.querySelector("linearGradient");
    const stops = Array.from(first!.querySelectorAll("stop"));

    // Same colour at two opacities — one token, so light/dark needs no second palette.
    expect(stops).toHaveLength(2);
    expect(stops[0].getAttribute("stop-color")).toBe(stops[1].getAttribute("stop-color"));
    expect(Number(stops[0].getAttribute("stop-opacity"))).toBeGreaterThan(
      Number(stops[1].getAttribute("stop-opacity")),
    );
    // A mark fading to fully transparent would lose its baseline.
    expect(Number(stops[1].getAttribute("stop-opacity"))).toBeGreaterThan(0);
  });

  it("assigns series colours in fixed slot order, not by rank (row 40)", () => {
    const twoSeries: ChartPayload = {
      ...BAR,
      series: [
        { name: "billed", data: [1, 2, 3, 4] },
        { name: "collected", data: [1, 2, 3, 4] },
      ],
    };
    const { container } = render(<ChartRenderer chart={twoSeries} />);

    const barFills = Array.from(container.querySelectorAll(".recharts-bar")).map((bar) =>
      bar.querySelector(".recharts-bar-rectangle path")?.getAttribute("fill"),
    );
    // Each bar paints through its own slot's gradient, in slot order.
    expect(barFills[0]).toMatch(/^url\(#chart-grad-.*-0\)$/);
    expect(barFills[1]).toMatch(/^url\(#chart-grad-.*-1\)$/);

    const stopFor = (index: number) =>
      container
        .querySelector(`linearGradient[id$="-${index}"] stop`)
        ?.getAttribute("stop-color");
    expect(stopFor(0)).toBe("var(--chart-series-1)");
    expect(stopFor(1)).toBe("var(--chart-series-2)");
  });

  it("fills the available width rather than a fixed pixel size (row 41)", () => {
    const { container } = render(<ChartRenderer chart={BAR} />);
    const figure = container.querySelector("figure");

    expect(figure).toHaveStyle({ width: "100%" });
    // Nothing may impose a width wider than the message column.
    expect(figure!.style.minWidth).toBe("");
  });

  it("renders nothing at all when there is no chart (row 42)", () => {
    const { container } = render(<ChartRenderer chart={null} />);
    expect(container.querySelector("figure")).toBeNull();
    expect(container).toBeEmptyDOMElement();
  });

  it("skips an unrecognised chart_type silently (row 43)", () => {
    const unknown = { ...BAR, chart_type: "sunburst" } as unknown as ChartPayload;
    const { container } = render(<ChartRenderer chart={unknown} />);

    expect(container).toBeEmptyDOMElement();
    expect(screen.queryByText(/error|unsupported|invalid/i)).toBeNull();
  });

  it("skips a payload whose series do not line up with its categories (row 43)", () => {
    const mismatched: ChartPayload = {
      ...BAR,
      series: [{ name: "amount", data: [1, 2] }],
    };
    const { container } = render(<ChartRenderer chart={mismatched} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("shows a legend when more than one series shares the chart", () => {
    const twoSeries: ChartPayload = {
      ...BAR,
      series: [
        { name: "billed", data: [1, 2, 3, 4] },
        { name: "collected", data: [4, 3, 2, 1] },
      ],
    };
    const { container } = render(<ChartRenderer chart={twoSeries} />);

    expect(container.querySelector(".recharts-legend-wrapper")).toBeTruthy();
    expect(screen.getByText("billed")).toBeInTheDocument();
    expect(screen.getByText("collected")).toBeInTheDocument();
  });

  it("folds a pie past the eighth slice into Other rather than inventing a hue", () => {
    const many: ChartPayload = {
      chart_type: "pie",
      title: "Spend by vendor",
      categories: Array.from({ length: 11 }, (_, i) => `V${i + 1}`),
      series: [{ name: "spend", data: Array.from({ length: 11 }, (_, i) => i + 1) }],
    };
    render(<ChartRenderer chart={many} />);

    expect(screen.getAllByText("Other").length).toBeGreaterThan(0);
    expect(screen.queryByText("V9")).toBeNull();
  });
});
