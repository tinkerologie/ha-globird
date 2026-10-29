import { render } from "lit";
import { afterEach, expect, it } from "vitest";
import {
  dailyChart,
  gasChart,
  gasReads,
  gasSeries,
  ticks,
} from "../../src/charts";
import { registerCards } from "../../src/index";
import type { DayRow, Series } from "../../src/types";
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
const fill = (el: Element) => el.getAttribute("style") ?? "";
const bars = (host: Element) =>
  [...host.querySelectorAll("rect:not(.hit)")].map((r) => ({
    y: Number(r.getAttribute("y")),
    h: Number(r.getAttribute("height")),
    fill: fill(r),
  }));
it("draws import above and export below the zero line, leaving gaps for missing days", () => {
  const rows: DayRow[] = [
    { day: "2030-04-28", usage: 3, export: 7 },
    { day: "2030-04-29" },
    { day: "2030-04-30", usage: 2, export: 1, controlled: 1 },
  ];
  const host = draw(dailyChart(rows, "usage", syntheticHass()));
  const drawn = bars(host);
  expect(drawn).toHaveLength(5);
  expect(host.querySelectorAll("line.zero")).toHaveLength(1);
  const zero = Number(host.querySelector("line.zero")?.getAttribute("y1"));
  const [imported, exported] = drawn;
  expect((imported?.y ?? 0) + (imported?.h ?? 0)).toBeCloseTo(zero);
  expect(exported?.y).toBeCloseTo(zero);
  expect(host.textContent).toContain("Controlled load");
  // The empty day keeps its hover target but draws no bar.
  expect(
    host.querySelectorAll("g")[1]?.querySelectorAll("rect:not(.hit)"),
  ).toHaveLength(0);
});
const registers: Series[] = [
  { key: "E1-Offpeak Usage", label: "Offpeak", direction: "import" },
  { key: "E1-Peak Usage", label: "Peak", direction: "import" },
  {
    key: "E1-ZeroHero",
    label: "ZeroHero",
    direction: "import",
    tracking: true,
  },
  { key: "B1-Feed", label: "Solar feed-in", direction: "export" },
];
it("stacks registers, marks tracking rows without adding them, and draws temperatures", () => {
  const rows: DayRow[] = [
    {
      day: "2030-04-30",
      usage: 3,
      export: 5,
      registers: {
        "E1-Offpeak Usage": 2,
        "E1-Peak Usage": 1,
        "E1-ZeroHero": 0.5,
        "B1-Feed": 5,
      },
      tempMin: 14,
      tempMax: 26,
    },
    {
      day: "2030-05-01",
      usage: 1,
      registers: { "E1-ZeroHero": 0 },
      tempMin: 15,
      tempMax: 27,
    },
  ];
  const host = draw(dailyChart(rows, "usage", syntheticHass(), { registers }));
  // Day one: two import segments and one export segment; day two: the total.
  expect(bars(host)).toHaveLength(4);
  expect(host.querySelectorAll("circle.marker")).toHaveLength(1);
  expect(host.querySelectorAll("path.temp")).toHaveLength(2);
  const legend = host.querySelector(".legend")?.textContent ?? "";
  for (const label of [
    "Offpeak",
    "Peak",
    "Solar feed-in",
    "ZeroHero (already counted)",
    "Max temp",
  ])
    expect(legend).toContain(label);
  expect(host.querySelector("g title")?.textContent).toContain("26 °C");
  const hidden = draw(
    dailyChart(rows, "usage", syntheticHass(), {
      registers,
      temperature: false,
    }),
  );
  expect(hidden.querySelectorAll("path.temp")).toHaveLength(0);
});
it("stacks charges above and credits below zero, and skips incomplete days", () => {
  const categories: Series[] = [
    { key: "SUPPLY", label: "Supply", direction: "import" },
    { key: "USAGE", label: "Usage", direction: "import" },
    { key: "ZEROHERO Credit", label: "ZeroHero credit", direction: "export" },
  ];
  const rows: DayRow[] = [
    {
      day: "2030-04-28",
      cost: 1.1,
      categories: { SUPPLY: 1.98, USAGE: 0.12, "ZEROHERO Credit": -1 },
    },
    { day: "2030-04-29", cost: -0.9 },
    { day: "2030-04-30", cost: 5, incomplete: true },
  ];
  const host = draw(dailyChart(rows, "cost", syntheticHass(), { categories }));
  const drawn = bars(host);
  expect(drawn).toHaveLength(4);
  const zero = Number(host.querySelector("line.zero")?.getAttribute("y1"));
  expect(drawn[2]?.y).toBeCloseTo(zero);
  expect(host.textContent).toContain("cost incomplete");
  expect(host.querySelector(".legend")?.textContent).toContain(
    "ZeroHero credit",
  );
});
const gasHistory = [
  {
    date: "2026-09-29",
    read_index: 752,
    source: "Distributor Read/Self Read Data",
  },
  { date: "2026-09-29", read_index: 752, source: "Invoice Read Data" },
  { date: "2026/10/27", read_index: 767, source: "Invoice Read Data" },
  { date: "bad", read_index: 1 },
  { date: "2026-10-28", read_index: "x" },
];
it("keeps one gas read per day and splits the chart by read source", () => {
  const reads = gasReads(gasHistory);
  expect(reads.map((r) => [r.day, r.index])).toEqual([
    ["2026-09-29", 752],
    ["2026-10-27", 767],
  ]);
  expect(gasReads(undefined)).toEqual([]);
  expect([...gasSeries(gasHistory).keys()]).toEqual([
    "Invoice Read Data",
    "Distributor Read/Self Read Data",
  ]);
  const host = draw(gasChart(gasHistory, syntheticHass()));
  expect(host.querySelectorAll("path.gas-line")).toHaveLength(2);
  expect(host.querySelectorAll("circle.gas-point")).toHaveLength(2);
  expect(host.querySelectorAll("rect.gas-point")).toHaveLength(1);
  const ys = [...host.querySelectorAll("circle.gas-point")].map((c) =>
    Number(c.getAttribute("cy")),
  );
  // Both reads sit inside the plot area, the later one higher up.
  expect(ys.every((y) => y > 8 && y < 136)).toBe(true);
  expect(ys[1]).toBeLessThan(ys[0] ?? 0);
  expect(host.querySelector(".legend")?.textContent).toContain("Invoice reads");
  expect(
    draw(gasChart(gasHistory.slice(0, 2), syntheticHass())).textContent,
  ).toBe("");
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
