import { describe, expect, it } from "vitest";
import {
  aligned,
  average,
  day,
  format,
  history,
  latestLabel,
  notices,
  number,
  services,
  statisticsRows,
  yesterday,
} from "../../src/data";
import { syntheticHass } from "../fixtures";

describe("calendar dates and HA-local presentation", () => {
  it("parses portal calendar dates without shifting timezones", () => {
    expect(day("2030/04/30")).toBe("2030-04-30");
    expect(day("2030-04-30T23:59:00Z")).toBe("2030-04-30");
    expect(day("2030/02/30")).toBeUndefined();
  });
  it("uses HA midnight across month end and DST, not the browser timezone", () => {
    const h = syntheticHass();
    expect(yesterday(h, new Date("2030-04-30T14:01:00Z"))).toBe("2030-04-30");
    expect(latestLabel("2030/04/30", h, new Date("2030-04-30T14:01:00Z"))).toBe(
      "Yesterday",
    );
    expect(
      latestLabel("2030/04/29", h, new Date("2030-04-30T14:01:00Z")),
    ).toContain("Latest available");
    h.config.time_zone = "America/New_York";
    expect(yesterday(h, new Date("2030-03-11T05:00:00Z"))).toBe("2030-03-10");
  });
  it("distinguishes zero, missing, invalid, and signed credits", () => {
    expect(number("0")).toBe(0);
    for (const v of [null, "", false, "unknown", "unavailable", Infinity])
      expect(number(v)).toBeUndefined();
    expect(format(-2.5, syntheticHass(), "AUD")).toBe("-$2.50");
    const h = syntheticHass();
    h.locale = { language: "de", number_format: "decimal_comma" };
    expect(format(1234.5, h)).toBe("1.234,5");
  });
});
describe("aligned telemetry", () => {
  it("groups services by account and service without translated entity names", () => {
    const all = services(syntheticHass());
    expect(all).toHaveLength(2);
    expect(all.map((s) => s.type)).toEqual(["electricity", "gas"]);
  });
  it("keeps controlled load separate and averages only actual readings", () => {
    const s = services(syntheticHass())[0];
    expect(s).toBeDefined();
    if (!s) throw new Error("Expected synthetic fixture value");
    const r = history(s);
    expect(average(r, "usage")).toEqual({ value: 2, days: 2 });
    expect(average(r, "controlled")).toEqual({ value: 3, days: 1 });
    expect(aligned(r)).toHaveLength(2);
  });
  it("excludes incomplete and supply-only days from comparisons", () => {
    const h = syntheticHass();
    const e = h.states["sensor.demo_cost_total"];
    if (!e) throw new Error("Expected synthetic fixture value");
    e.attributes.incomplete_days = ["2030/04/30"];
    e.attributes.daily_totals = [
      { date: "2030/04/29", amount: 1 },
      { date: "2030/04/30", amount: 3 },
      { date: "2030/05/01", amount: 2 },
    ];
    const s = services(h)[0];
    if (!s) throw new Error("Expected synthetic fixture value");
    const r = history(s);
    expect(aligned(r)).toHaveLength(1);
    expect(r.at(-1)?.usage).toBeUndefined();
    expect(notices(h, s).join()).toContain("incomplete");
  });
  it("reads statistics change without cumulative sum arithmetic", () => {
    const h = syntheticHass(),
      s = services(h)[0];
    if (!s) throw new Error("Expected synthetic fixture value");
    const rows = statisticsRows(
      {
        "globird:demo_import": [
          { start: Date.parse("2030-04-29T14:00Z"), change: 0 },
          { start: Date.parse("2030-04-30T14:00Z"), change: 4 },
        ],
      },
      s,
      h,
    );
    expect(rows.map((r) => r.usage)).toEqual([0, 4]);
    expect(rows[0]?.day).toBe("2030-04-30");
  });
  it("reports stale refresh with last success, without private errors", () => {
    const h = syntheticHass();
    const e = h.states["sensor.demo_refresh_status"];
    if (!e) throw new Error("Expected synthetic fixture value");
    e.state = "error";
    e.attributes.refresh_error = "private exception";
    const s = services(h)[0];
    if (!s) throw new Error("Expected synthetic fixture value");
    expect(notices(h, s).join()).toContain("Last successful refresh");
    expect(notices(h, s).join()).not.toContain("private exception");
  });
});

it("never exposes a cumulative sum as usage when change is missing", () => {
  const h = syntheticHass(),
    s = services(h)[0];
  if (!s) throw new Error("fixture missing");
  const cumulative = { start: Date.parse("2030-04-29T14:00Z"), sum: 987654 };
  expect(statisticsRows({ "globird:demo_import": [cumulative] }, s, h)).toEqual(
    [],
  );
});
