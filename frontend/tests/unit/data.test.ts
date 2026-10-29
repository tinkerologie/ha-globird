import { describe, expect, it } from "vitest";
import {
  aligned,
  average,
  breakdown,
  day,
  format,
  history,
  latestLabel,
  midnight,
  notices,
  number,
  services,
  statisticsRows,
  temperatures,
  withTemperatures,
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
    expect(notices(h, s).join()).toContain("last successful refresh");
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

it("builds explicit local midnight bounds across DST changes", () => {
  const h = syntheticHass();
  h.config.time_zone = "America/New_York";
  expect(midnight(h, "2030-03-10")).toBe("2030-03-10T05:00:00.000Z");
  expect(midnight(h, "2030-03-11")).toBe("2030-03-11T04:00:00.000Z");
});

it("does not expose empty register-only groups as selectable services", () => {
  const h = syntheticHass();
  h.states["sensor.register_only"] = {
    entity_id: "sensor.register_only",
    state: "2",
    attributes: {
      globird_sensor_key: "register",
      account_id: "demo-account",
      account_service_id: "register-only",
      service_type: "Electricity",
    },
  };
  expect(services(h)).toHaveLength(2);
});

it("keeps older and cost-only incomplete recorder days out of comparisons", () => {
  const h = syntheticHass(),
    service = services(h)[0],
    cost = h.states["sensor.demo_cost_total"];
  if (!service || !cost) throw new Error("fixture missing");
  cost.attributes.incomplete_days = ["2030/04/10", "2030-04-11"];
  const result = {
    "globird:demo_import": [
      { start: Date.parse("2030-04-09T14:00Z"), change: 1 },
    ],
    "globird:demo_cost": [
      { start: Date.parse("2030-04-09T14:00Z"), change: 9 },
      { start: Date.parse("2030-04-10T14:00Z"), change: 2 },
    ],
  };
  const rows = statisticsRows(result, service, h);
  expect(rows).toHaveLength(2);
  expect(rows.every((r) => r.incomplete && r.cost === undefined)).toBe(true);
  expect(aligned(rows)).toEqual([]);
});
it("does not attribute an ambiguous connection failure to a healthy account", () => {
  const h = syntheticHass(),
    service = services(h)[0];
  if (!service) throw new Error("fixture missing");
  h.states["sensor.other_refresh"] = {
    entity_id: "sensor.other_refresh",
    state: "error",
    attributes: {
      globird_sensor_key: "refresh_status",
      last_successful_refresh: "2030-04-01T00:00:00Z",
    },
  };
  const warnings = notices(h, service).join();
  expect(warnings).toContain("affected account cannot be identified");
  expect(warnings).not.toContain("Showing the last successful data");
});

it("breaks days into registers and charge categories from statistics", () => {
  const h = syntheticHass();
  const s = services(h).find((x) => x.type === "electricity");
  if (!s?.entities.usage_total || !s.entities.cost_total)
    throw new Error("fixture missing");
  s.entities.usage_total.attributes.register_statistics = [
    {
      key: "E1-Peak Usage",
      chargeType: "Peak Usage",
      usage_class: "general_import",
      statistic_id: "globird:peak",
    },
    {
      key: "E1-ZeroHero",
      chargeType: "ZeroHero",
      usage_class: "tracking",
      statistic_id: "globird:zh",
    },
    { key: 7 },
  ];
  s.entities.cost_total.attributes.category_statistics = [
    { category: "ZEROHERO Credit", statistic_id: "globird:zhc" },
    { category: "SUPPLY", statistic_id: "globird:supply" },
    { category: "broken" },
  ];
  const { registers, categories } = breakdown(s);
  expect(registers.map((r) => [r.label, r.direction, r.tracking])).toEqual([
    ["Peak", "import", false],
    ["ZeroHero", "import", true],
  ]);
  expect(categories.map((c) => [c.label, c.direction])).toEqual([
    ["Supply", "import"],
    ["ZeroHero credit", "export"],
  ]);
  const start = Date.parse("2030-04-29T14:00Z");
  const rows = statisticsRows(
    {
      "globird:peak": [{ start, change: 1.5 }],
      "globird:zh": [{ start, change: 0.5 }],
      "globird:supply": [{ start, change: 1.98 }],
      "globird:zhc": [{ start, change: -1 }],
    },
    s,
    h,
  );
  expect(rows[0]?.registers).toEqual({
    "E1-Peak Usage": 1.5,
    "E1-ZeroHero": 0.5,
  });
  expect(rows[0]?.categories).toEqual({ SUPPLY: 1.98, "ZEROHERO Credit": -1 });
});

it("reads daily temperatures from the account's weather summary", () => {
  const h = syntheticHass();
  const s = services(h)[0];
  if (!s) throw new Error("fixture missing");
  h.states["sensor.weather"] = {
    entity_id: "sensor.weather",
    state: "26",
    attributes: {
      globird_sensor_key: "weather_summary",
      account_id: s.accountId,
      daily: [
        { dateAsDate: "2030-04-30T00:00:00", obMinTemp: 14.2, obMaxTemp: 26.1 },
        { dateAsDate: "bad", obMinTemp: 1 },
      ],
    },
  };
  const temps = temperatures(h, s);
  expect([...temps.entries()]).toEqual([
    ["2030-04-30", { min: 14.2, max: 26.1 }],
  ]);
  expect(
    withTemperatures([{ day: "2030-04-30" }, { day: "2030-05-01" }], temps),
  ).toEqual([
    { day: "2030-04-30", tempMin: 14.2, tempMax: 26.1 },
    { day: "2030-05-01" },
  ]);
});
