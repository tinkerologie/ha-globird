import { render } from "lit";
import { afterEach, expect, it } from "vitest";
import { dailyChart, gasChart, gasReads, ticks } from "../../src/charts";
import { registerCards } from "../../src/index";
import type { DayRow } from "../../src/types";
import { syntheticHass } from "../fixtures";

afterEach(() => document.body.replaceChildren());
function draw(template: unknown) {
  const host = document.createElement("div");
  render(template, host);
  document.body.append(host);
  return host;
}
it("chooses round ticks that always include zero", () => {
  expect(ticks(-59, 20)).toEqual([-60, -40, -20, 0, 20]);
  expect(ticks(0, 2.4)).toEqual([0, 1, 2, 3]);
  expect(ticks(0, 1.9)).toEqual([0, 0.5, 1, 1.5, 2]);
  expect(ticks(0, 0)).toEqual([0, 0.25]);
  expect(ticks(746, 773, 4, false)).toEqual([740, 750, 760, 770, 780]);
});
it("draws import above and export below the zero line, leaving gaps for missing days", () => {
  const rows: DayRow[] = [
    { day: "2030-04-28", usage: 3, export: 7 },
    { day: "2030-04-29" },
    { day: "2030-04-30", usage: 2, export: 1, controlled: 1 },
  ];
  const host = draw(dailyChart(rows, "usage", syntheticHass()));
  expect(host.querySelectorAll("rect.import")).toHaveLength(2);
  expect(host.querySelectorAll("rect.export")).toHaveLength(2);
  expect(host.querySelectorAll("rect.controlled")).toHaveLength(1);
  expect(host.querySelectorAll("line.zero")).toHaveLength(1);
  const zero = Number(host.querySelector("line.zero")?.getAttribute("y1"));
  const imported = host.querySelector("rect.import");
  const exported = host.querySelector("rect.export");
  expect(
    Number(imported?.getAttribute("y")) +
      Number(imported?.getAttribute("height")),
  ).toBeCloseTo(zero);
  expect(Number(exported?.getAttribute("y"))).toBeCloseTo(zero);
  expect(host.textContent).toContain("Controlled load");
});
it("shows credits below zero and skips incomplete cost days", () => {
  const rows: DayRow[] = [
    { day: "2030-04-28", cost: 2.1 },
    { day: "2030-04-29", cost: -0.9 },
    { day: "2030-04-30", cost: 5, incomplete: true },
  ];
  const host = draw(dailyChart(rows, "cost", syntheticHass()));
  expect(host.querySelectorAll("rect.cost")).toHaveLength(1);
  expect(host.querySelectorAll("rect.credit")).toHaveLength(1);
  expect(host.textContent).toContain("cost incomplete");
});
it("keeps one gas read per day and needs two reads for a chart", () => {
  const reads = gasReads([
    { date: "2026-09-29", read_index: 752, source: "Distributor" },
    { date: "2026-09-29", read_index: 752, source: "Invoice" },
    { date: "2026-10-27", read_index: 767, source: "Invoice" },
    { date: "bad", read_index: 1 },
    { date: "2026-10-28", read_index: "x" },
  ]);
  expect(reads.map((r) => [r.day, r.index])).toEqual([
    ["2026-09-29", 752],
    ["2026-10-27", 767],
  ]);
  expect(gasReads(undefined)).toEqual([]);
  const host = draw(gasChart(reads, syntheticHass()));
  expect(host.querySelectorAll("circle.gas-point")).toHaveLength(2);
  const ys = [...host.querySelectorAll("circle.gas-point")].map((c) =>
    Number(c.getAttribute("cy")),
  );
  // Both reads sit inside the plot area, the later one higher up.
  expect(ys.every((y) => y > 8 && y < 136)).toBe(true);
  expect(ys[1]).toBeLessThan(ys[0] ?? 0);
  expect(draw(gasChart(reads.slice(0, 1), syntheticHass())).textContent).toBe(
    "",
  );
});
it("suggests each card only for its own GloBird sensors", () => {
  registerCards();
  const hass = syntheticHass();
  const byType = Object.fromEntries(
    (window.customCards ?? []).map((c) => [c.type, c.getEntitySuggestion]),
  );
  expect(
    byType["globird-account-card"]?.(hass, "sensor.demo_dashboard_balance"),
  ).toEqual({
    config: {
      type: "custom:globird-account-card",
      entity: "sensor.demo_dashboard_balance",
    },
  });
  expect(
    byType["globird-usage-cost-card"]?.(hass, "sensor.demo_dashboard_balance"),
  ).toBeNull();
  expect(byType["globird-account-card"]?.(hass, "light.kitchen")).toBeNull();
});
