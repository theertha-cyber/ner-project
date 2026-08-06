import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetricsPanel } from "./MetricsPanel";
import type { SideMetric, SideRow } from "@/types/dashboard";

const metrics: [SideMetric, SideMetric, SideMetric] = [
  { k: "prec", v: "0.92" },
  { k: "rec", v: "0.89" },
  { k: "loss", v: ".021" },
];

const rows: SideRow[] = [
  { label: "Northwind", val: "18.4 / 25 GB", pct: 74, c: "var(--primary)" },
  { label: "Umbrella", val: "9.1 / 15 GB", pct: 61, c: "var(--info)" },
];

describe("MetricsPanel", () => {
  it("renders header and big number", () => {
    render(
      <MetricsPanel
        sideTop="Platform health"
        sideMeta="uptime 30d"
        big="99.9"
        bigUnit="% SLA"
        bar={62}
        sideMetrics={metrics}
        sideBot="Storage by tenant"
        sideRows={rows}
      />
    );
    expect(screen.getByText("Platform health")).toBeInTheDocument();
    expect(screen.getByText("99.9")).toBeInTheDocument();
    expect(screen.getByText("% SLA")).toBeInTheDocument();
  });

  it("renders side metric rows", () => {
    render(
      <MetricsPanel
        sideTop="Health"
        sideMeta="meta"
        big="0"
        bigUnit=""
        bar={0}
        sideMetrics={metrics}
        sideBot="Storage"
        sideRows={rows}
      />
    );
    expect(screen.getByText("prec")).toBeInTheDocument();
    expect(screen.getByText("0.92")).toBeInTheDocument();
  });

  it("renders sideRows when provided", () => {
    render(
      <MetricsPanel
        sideTop="Health"
        sideMeta="meta"
        big="0"
        bigUnit=""
        bar={0}
        sideMetrics={metrics}
        sideBot="Storage by tenant"
        sideRows={rows}
      />
    );
    expect(screen.getByText("Northwind")).toBeInTheDocument();
    expect(screen.getByText("Umbrella")).toBeInTheDocument();
  });

  it("does not render sideBot section when sideRows is empty", () => {
    render(
      <MetricsPanel
        sideTop="Health"
        sideMeta="meta"
        big="0"
        bigUnit=""
        bar={0}
        sideMetrics={metrics}
        sideBot="Storage"
        sideRows={[]}
      />
    );
    expect(screen.queryByText("Storage")).not.toBeInTheDocument();
  });

  it("sideMetrics render as inline flex row (not stacked column)", () => {
    render(
      <MetricsPanel
        sideTop="Health"
        sideMeta="meta"
        big="0"
        bigUnit=""
        bar={0}
        sideMetrics={metrics}
        sideBot="Storage"
        sideRows={[]}
      />
    );
    expect(screen.getByText("prec")).toBeInTheDocument();
    expect(screen.getByText("rec")).toBeInTheDocument();
    expect(screen.getByText("loss")).toBeInTheDocument();
  });

  it("progress bar has 8px height", () => {
    const { container } = render(
      <MetricsPanel
        sideTop="Health"
        sideMeta="meta"
        big="0"
        bigUnit=""
        bar={62}
        sideMetrics={metrics}
        sideBot="Storage"
        sideRows={[]}
      />
    );
    const barContainers = container.querySelectorAll("div > div");
    let found = false;
    barContainers.forEach((div) => {
      if (div.style.height === "8px" && div.style.borderRadius === "3px") {
        found = true;
      }
    });
    expect(found).toBe(true);
  });

  it("header uses stacked layout (title above meta, not flex space-between)", () => {
    render(
      <MetricsPanel
        sideTop="Platform health"
        sideMeta="uptime 30d"
        big="0"
        bigUnit=""
        bar={0}
        sideMetrics={metrics}
        sideBot="Storage"
        sideRows={[]}
      />
    );
    const top = screen.getByText("Platform health");
    const meta = screen.getByText("uptime 30d");
    expect(top).toBeInTheDocument();
    expect(meta).toBeInTheDocument();
    expect(top.style.display).toBe("block");
    expect(meta.style.display).toBe("block");
  });

  it("renders an Offline sideMetrics value in the red/bad status colour", () => {
    const offlineMetrics: [SideMetric, SideMetric, SideMetric] = [
      { k: "gateway", v: "Online" },
      { k: "chat api", v: "Offline" },
      { k: "extraction", v: "Online" },
    ];
    render(
      <MetricsPanel
        sideTop="Platform Health"
        sideMeta="live service checks"
        big="Degraded"
        bigUnit=""
        bar={50}
        sideMetrics={offlineMetrics}
        sideBot="Backing services"
        sideRows={[]}
      />
    );
    const value = screen.getByText("Offline");
    expect(value.style.color).toBe("var(--bad, #b91c1c)");
  });

  it("renders big status with severity colour for Critical/Degraded/Healthy", () => {
    const { rerender } = render(
      <MetricsPanel
        sideTop="Platform Health"
        sideMeta="live service checks"
        big="Critical"
        bigUnit=""
        bar={0}
        sideMetrics={metrics}
        sideBot="Backing services"
        sideRows={[]}
      />
    );
    expect(screen.getByText("Critical").style.color).toBe("var(--bad, #b91c1c)");

    rerender(
      <MetricsPanel
        sideTop="Platform Health"
        sideMeta="live service checks"
        big="Degraded"
        bigUnit=""
        bar={50}
        sideMetrics={metrics}
        sideBot="Backing services"
        sideRows={[]}
      />
    );
    expect(screen.getByText("Degraded").style.color).toBe("var(--warn, #b45309)");

    rerender(
      <MetricsPanel
        sideTop="Platform Health"
        sideMeta="live service checks"
        big="Healthy"
        bigUnit=""
        bar={100}
        sideMetrics={metrics}
        sideBot="Backing services"
        sideRows={[]}
      />
    );
    expect(screen.getByText("Healthy").style.color).toBe("var(--color-delta-up, #15803d)");
  });
});
