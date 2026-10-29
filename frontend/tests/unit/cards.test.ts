import { afterEach, expect, it, vi } from "vitest";
import type { GloBirdCard } from "../../src/cards/base";
import type { CardEditor } from "../../src/editors/card-editor";
import { registerCards } from "../../src/index";
import type { CardConfig, Hass } from "../../src/types";
import { syntheticHass } from "../fixtures";

afterEach(() => document.body.replaceChildren());
async function card(
  tag: string,
  hass: Hass | null = syntheticHass(),
  config: Partial<CardConfig> = {},
) {
  const c = document.createElement(tag) as GloBirdCard;
  c.setConfig(Object.freeze({ type: `custom:${tag}`, ...config }));
  c.hass = hass ?? undefined;
  document.body.append(c);
  await c.updateComplete;
  return c;
}
it("registers four cards once and supports Sections and masonry", async () => {
  registerCards();
  registerCards();
  expect(window.customCards).toHaveLength(4);
  for (const meta of window.customCards ?? []) {
    const c = await card(meta.type);
    expect(c.getGridOptions()).toMatchObject({ columns: 12, rows: "auto" });
    expect(c.getCardSize()).toBeGreaterThan(0);
    expect(c.shadowRoot?.textContent).toContain("GloBird Energy");
  }
});
it("opens more-info using native buttons and a composed event", async () => {
  const c = await card("globird-usage-cost-card");
  const handler = vi.fn();
  c.addEventListener("hass-more-info", handler);
  c.shadowRoot?.querySelector<HTMLButtonElement>("button.metric")?.click();
  expect(handler).toHaveBeenCalled();
});
it("does not label gas meter indexes as daily consumption or missing reads as zero", async () => {
  const c = await card("globird-latest-day-card", syntheticHass(), {
    entity: "sensor.demo_latest_gas_reading_gas",
  });
  expect(c.shadowRoot?.textContent).toContain("Gas meter reading");
  expect(c.shadowRoot?.textContent).toContain("No data");
  expect(c.shadowRoot?.textContent).toContain("not daily consumption");
});
it("rejects bad configuration and never mutates a frozen config", async () => {
  const c = await card("globird-usage-cost-card");
  expect(() =>
    c.setConfig({ type: "custom:globird-usage-cost-card", history_days: 0 }),
  ).toThrow();
  expect(() =>
    c.setConfig({ type: "x", history_source: "bad" as "attributes" }),
  ).toThrow();
});
it("requires explicit selection across accounts and does not silently fall back for a missing entity", async () => {
  const h = syntheticHass();
  const original = h.states["sensor.demo_usage_total"];
  if (!original) throw new Error("Expected synthetic fixture value");
  h.states["sensor.second"] = {
    ...original,
    entity_id: "sensor.second",
    attributes: { ...original.attributes, account_id: "second-account" },
  };
  const c = await card("globird-latest-day-card", h);
  expect(c.shadowRoot?.textContent).toContain("Select a GloBird service");
  const missing = await card("globird-latest-day-card", syntheticHass(), {
    entity: "sensor.missing",
  });
  expect(missing.shadowRoot?.textContent).toContain("Select a GloBird service");
});
it("renders loading, unavailable, zero, and negative net usage truthfully", async () => {
  expect(
    (await card("globird-latest-day-card", null)).shadowRoot?.textContent,
  ).toContain("Waiting for GloBird");
  const h = syntheticHass(),
    entity = h.states["sensor.demo_latest_day_usage"];
  if (!entity) throw new Error("Expected synthetic fixture value");
  const c = await card("globird-latest-day-card", h);
  expect(c.shadowRoot?.textContent).toContain("-5 kWh");
  entity.state = "unavailable";
  c.hass = { ...h, states: { ...h.states, [entity.entity_id]: { ...entity } } };
  await c.updateComplete;
  expect(c.shadowRoot?.textContent).toContain("Unavailable");
});
it("editor emits immutable full configurations with native labelled fields", async () => {
  const editor = document.createElement("globird-card-editor") as CardEditor;
  const config = Object.freeze({
    type: "custom:globird-latest-day-card",
    title: "Before",
  });
  editor.setConfig(config);
  editor.hass = syntheticHass();
  document.body.append(editor);
  await editor.updateComplete;
  const handler = vi.fn();
  editor.addEventListener("config-changed", handler);
  const input = editor.shadowRoot?.querySelector<HTMLInputElement>(
    'input:not([type="number"])',
  );
  if (!input) throw new Error("missing title field");
  input.value = "After";
  input.dispatchEvent(new Event("input"));
  expect(config.title).toBe("Before");
  expect(handler.mock.calls[0]?.[0].detail.config.title).toBe("After");
  expect(handler.mock.calls[0]?.[0].composed).toBe(true);
});
it("fetches optional statistics once and discards results after service changes", async () => {
  let resolve: ((r: Record<string, unknown>) => void) | undefined;
  const h = syntheticHass();
  const calls: Record<string, unknown>[] = [];
  h.callWS = <T>(r: Record<string, unknown>) => {
    calls.push(r);
    return new Promise<T>((res) => {
      resolve = res as typeof resolve;
    });
  };
  const c = await card("globird-electricity-usage-card", h, {
    history_source: "statistics",
    history_days: 31,
  });
  await c.updateComplete;
  expect(calls).toHaveLength(1);
  expect(calls[0]?.types).toEqual(["change"]);
  c.setConfig({
    type: "custom:globird-electricity-usage-card",
    entity: "sensor.demo_latest_gas_reading_gas",
    history_source: "statistics",
  });
  await c.updateComplete;
  resolve?.({});
  await Promise.resolve();
  await c.updateComplete;
  expect(c.shadowRoot?.textContent).toContain("Gas meter reading");
});

it("does not pair two missing dates as a matching cost or export day", async () => {
  const h = syntheticHass();
  for (const key of [
    "latest_day_usage",
    "latest_day_cost",
    "latest_day_solar_export",
  ]) {
    const e = h.states[`sensor.demo_${key}`];
    if (!e) throw new Error("fixture missing");
    delete e.attributes.latest_day;
  }
  const c = await card("globird-latest-day-card", h);
  const metrics = [...(c.shadowRoot?.querySelectorAll(".metric") ?? [])];
  expect(
    metrics.find((e) => e.textContent?.includes("Net cost"))?.textContent,
  ).toContain("No data");
  expect(
    metrics.find((e) => e.textContent?.includes("Net grid usage"))?.textContent,
  ).toContain("No data");
});
it("preserves the selected electricity service when switching to gas and back", async () => {
  const h = syntheticHass();
  const original = h.states["sensor.demo_usage_total"];
  if (!original) throw new Error("fixture missing");
  h.states["sensor.other_electric"] = {
    ...original,
    entity_id: "sensor.other_electric",
    attributes: {
      ...original.attributes,
      account_service_id: "second-electric",
    },
  };
  const c = await card("globird-latest-day-card", h, {
    entity: "sensor.demo_latest_day_usage",
  });
  c.shadowRoot?.querySelector<HTMLInputElement>('input[value="gas"]')?.click();
  await c.updateComplete;
  const electricity = c.shadowRoot?.querySelector<HTMLInputElement>(
    'input[value="electricity"]',
  );
  expect(electricity?.disabled).toBe(false);
  electricity?.click();
  await c.updateComplete;
  expect(c.shadowRoot?.textContent).toContain("-5");
  expect(
    c.shadowRoot?.querySelector('select[aria-label="Electricity service"]'),
  ).toBeTruthy();
});
it("rejects invalid history input visibly without emitting a changed config", async () => {
  const editor = document.createElement("globird-card-editor") as CardEditor;
  editor.setConfig({
    type: "custom:globird-electricity-usage-card",
    history_days: 10,
  });
  editor.hass = syntheticHass();
  document.body.append(editor);
  await editor.updateComplete;
  const input = editor.shadowRoot?.querySelector<HTMLInputElement>(
    'input[type="number"]',
  );
  if (!input) throw new Error("missing history control");
  const fn = vi.fn();
  editor.addEventListener("config-changed", fn);
  input.value = "40";
  input.dispatchEvent(new Event("change"));
  expect(input.value).toBe("10");
  expect(fn).not.toHaveBeenCalled();
});
it("switches the daily chart between usage and cost", async () => {
  const c = await card("globird-electricity-usage-card");
  const root = c.shadowRoot;
  const cost = root?.querySelector<HTMLInputElement>(
    'input[name="chart-mode"][value="cost"]',
  );
  if (!cost) throw new Error("missing chart mode switch");
  cost.click();
  await c.updateComplete;
  expect(root?.querySelector(".legend")?.textContent).toContain("Net cost");
});
it("shows data notices as alerts with an icon", async () => {
  const c = await card("globird-latest-day-card", syntheticHass(), {
    entity: "sensor.demo_latest_gas_reading_gas",
  });
  const alertEl = c.shadowRoot?.querySelector(".alert");
  expect(alertEl?.getAttribute("role")).toBe("status");
  expect(alertEl?.querySelector("svg")).not.toBeNull();
});
