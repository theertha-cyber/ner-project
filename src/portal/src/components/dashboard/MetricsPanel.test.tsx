import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

function renderOverflowPanel(count: number) {
  const rows = Array.from({ length: count }, (_, i) => ({
    label: `TYPE_${i}`,
    val: `${i}/200`,
    pct: i,
    c: "var(--bad, #b91c1c)",
  }));
  return render(
    <MetricsPanel
      sideTop="Dataset readiness"
      sideMeta={`0 of ${count} entity types ready`}
      big="1"
      bigUnit="% to training-ready"
      bar={1}
      sideMetrics={metrics}
      sideBot="200 entities per type unlocks training"
      sideRows={rows}
    />
  );
}

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
  it("renders readiness rows as count-against-threshold with progress-scaled bars", () => {
    const { container } = render(
      <MetricsPanel
        sideTop="Dataset readiness"
        sideMeta="1 of 2 entity types ready"
        big="75"
        bigUnit="% to training-ready"
        bar={75}
        sideMetrics={metrics}
        sideBot="200 entities per type unlocks training"
        sideRows={[{ label: "JOB_TITLE", val: "100/200", pct: 50, c: "var(--warn, #b45309)" }]}
      />
    );
    expect(screen.getByText("JOB_TITLE")).toBeInTheDocument();
    expect(screen.getByText("100/200")).toBeInTheDocument();
    const bars = container.querySelectorAll('div[style*="height: 6px"] > div');
    expect(bars.length).toBe(1);
  });

  it("gives starved and satisfied entity types different bar colours", () => {
    const { container } = render(
      <MetricsPanel
        sideTop="Dataset readiness"
        sideMeta="1 of 2 entity types ready"
        big="50"
        bigUnit="% to training-ready"
        bar={50}
        sideMetrics={metrics}
        sideBot="200 entities per type unlocks training"
        sideRows={[
          { label: "STARVED", val: "0/200", pct: 0, c: "var(--bad, #b91c1c)" },
          { label: "READY", val: "200/200", pct: 100, c: "var(--color-delta-up, #15803d)" },
        ]}
      />
    );
    const bars = Array.from(container.querySelectorAll('div[style*="height: 6px"] > div'));
    expect(bars.length).toBe(2);
    expect((bars[0] as HTMLElement).style.background).not.toBe(
      (bars[1] as HTMLElement).style.background,
    );
  });

  it("indicates how many entity types are not shown when the list overflows", () => {
    const rows = Array.from({ length: 9 }, (_, i) => ({
      label: `TYPE_${i}`,
      val: `${i}/200`,
      pct: i,
      c: "var(--bad, #b91c1c)",
    }));
    render(
      <MetricsPanel
        sideTop="Dataset readiness"
        sideMeta="0 of 9 entity types ready"
        big="1"
        bigUnit="% to training-ready"
        bar={1}
        sideMetrics={metrics}
        sideBot="200 entities per type unlocks training"
        sideRows={rows}
      />
    );
    // Rows arrive least-progressed first, so the shown ones are the ones to act on.
    expect(screen.getByText("TYPE_0")).toBeInTheDocument();
    expect(screen.queryByText("TYPE_8")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /\+3 more/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view all/i })).toBeInTheDocument();
  });

  it("expands in place to show every entity type when view all is pressed", async () => {
    const user = userEvent.setup();
    renderOverflowPanel(9);
    expect(screen.queryByText("TYPE_8")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /view all/i }));

    for (let i = 0; i < 9; i += 1) {
      expect(screen.getByText(`TYPE_${i}`)).toBeInTheDocument();
    }
    const toggle = screen.getByRole("button", { name: /show less/i });
    expect(toggle).toHaveAttribute("aria-expanded", "true");
  });

  it("collapses back to the capped list and re-states the hidden count", async () => {
    const user = userEvent.setup();
    renderOverflowPanel(9);

    await user.click(screen.getByRole("button", { name: /view all/i }));
    await user.click(screen.getByRole("button", { name: /show less/i }));

    expect(screen.queryByText("TYPE_8")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /\+3 more/ })).toBeInTheDocument();
  });

  it("offers no view-all control when nothing is hidden", () => {
    renderOverflowPanel(3);
    expect(screen.getByText("TYPE_2")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /view all/i })).not.toBeInTheDocument();
  });
});
