import { html, nothing, svg } from "lit";
import { dateLabel, format } from "./data";
import type { DayRow, Hass } from "./types";

export type ChartMode = "usage" | "cost";
export interface GasRead {
  day: string;
  index: number;
  source?: string;
}

// Plot area of the 320 × 168 viewBox; labels sit outside it.
const LEFT = 36,
  RIGHT = 312,
  TOP = 8,
  BOTTOM = 136;

/** Round axis ticks (1, 2, 2.5 or 5 × 10ⁿ) covering ``min`` to ``max``,
 * and zero unless ``zero`` is false. */
export function ticks(
  min: number,
  max: number,
  count = 4,
  zero = true,
): number[] {
  const lo = zero ? Math.min(0, min) : min,
    hi = zero ? Math.max(0, max) : max;
  const span = hi - lo || 1;
  const raw = span / count;
  const power = 10 ** Math.floor(Math.log10(raw));
  const step =
    [1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => s >= raw) ??
    10 * power;
  const first = Math.floor(lo / step) * step;
  const last = Math.ceil(hi / step) * step;
  const result: number[] = [];
  for (let v = first; v <= last + step * 1e-9; v += step)
    result.push(Number(v.toPrecision(12)));
  if (result.length < 2) result.push(first + step);
  return result;
}

function axis(values: number[], hass: Hass, unit?: string) {
  const t = ticks(Math.min(...values), Math.max(...values));
  const lo = t[0] ?? 0,
    hi = t.at(-1) ?? 1;
  const y = (v: number) =>
    BOTTOM - ((v - lo) / (hi - lo || 1)) * (BOTTOM - TOP);
  const lines = t.map(
    (v) =>
      svg`<line class=${v === 0 ? "zero" : "grid"} x1=${LEFT} x2=${RIGHT} y1=${y(v)} y2=${y(v)}/><text x=${LEFT - 4} y=${y(v) + 3} text-anchor="end">${unit === "AUD" ? `$${format(v, hass)}` : format(v, hass)}</text>`,
  );
  return { y, lines };
}

/** A short calendar date, like "28 Sep", for axis ticks. */
function shortDate(iso: string | undefined, hass: Hass) {
  if (!iso) return "";
  return new Intl.DateTimeFormat(hass.locale?.language ?? "en", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  }).format(new Date(`${iso}T00:00:00Z`));
}

function dateTicks(days: string[], x: (i: number) => number, hass: Hass) {
  if (!days.length) return nothing;
  const count = Math.min(days.length, 4);
  const picks =
    count === 1
      ? [0]
      : Array.from({ length: count }, (_, k) =>
          Math.round((k * (days.length - 1)) / (count - 1)),
        );
  return [...new Set(picks)].map(
    (i, k, all) =>
      svg`<text x=${x(i)} y="152" text-anchor=${k === 0 && all.length > 1 ? "start" : k === all.length - 1 && all.length > 1 ? "end" : "middle"}>${shortDate(days[i], hass)}</text>`,
  );
}

/** Daily bars around a zero line: import above and export below, or net cost
 * above and credits below. Missing days leave a gap, never a zero bar. */
export function dailyChart(rows: DayRow[], mode: ChartMode, hass: Hass) {
  const label =
    mode === "usage"
      ? "Daily grid import above the zero line and solar export below it, in kilowatt-hours. Values are listed in the daily readings table."
      : "Daily net cost, with credits below the zero line, in Australian dollars. Values are listed in the daily readings table.";
  const values =
    mode === "usage"
      ? rows.flatMap((r) => [
          (r.usage ?? 0) + (r.controlled ?? 0),
          -(r.export ?? 0),
        ])
      : rows.map((r) => (r.incomplete ? 0 : (r.cost ?? 0)));
  const { y, lines } = axis(values, hass, mode === "cost" ? "AUD" : undefined);
  const slot = (RIGHT - LEFT) / Math.max(rows.length, 1);
  const width = Math.max(2, Math.min(slot * 0.7, 14));
  const x = (i: number) => LEFT + slot * i + slot / 2;
  const bar = (cls: string, i: number, from: number, to: number) =>
    svg`<rect class=${cls} x=${x(i) - width / 2} y=${Math.min(y(from), y(to))} width=${width} height=${Math.max(0, Math.abs(y(to) - y(from)))} rx=${Math.min(3, width / 3)}/>`;
  const bars = rows.map((r, i) => {
    const day = dateLabel(r.day, hass);
    if (mode === "cost") {
      const tip = r.incomplete
        ? `${day}: cost incomplete`
        : `${day}: ${r.cost === undefined ? "no cost data" : format(r.cost, hass, "AUD")}`;
      return svg`<g><title>${tip}</title>${r.cost === undefined || r.incomplete ? nothing : bar(r.cost < 0 ? "credit" : "cost", i, 0, r.cost)}</g>`;
    }
    const imported = r.usage ?? 0;
    const tip = `${day}: import ${r.usage === undefined ? "no data" : format(r.usage, hass, "kWh")}; export ${r.export === undefined ? "no data" : format(r.export, hass, "kWh")}${r.controlled === undefined ? "" : `; controlled load ${format(r.controlled, hass, "kWh")}`}`;
    return svg`<g><title>${tip}</title>${r.usage === undefined ? nothing : bar("import", i, 0, imported)}${r.controlled === undefined ? nothing : bar("controlled", i, imported, imported + r.controlled)}${r.export === undefined ? nothing : bar("export", i, 0, -r.export)}</g>`;
  });
  const legend =
    mode === "usage"
      ? html`<div class="legend"><span class="import">Grid import</span>${rows.some((r) => r.controlled !== undefined) ? html`<span class="controlled">Controlled load</span>` : nothing}<span class="export">Solar export</span><span class="unit-label">kWh</span></div>`
      : html`<div class="legend"><span class="cost">Net cost</span><span class="credit">Credit</span><span class="unit-label">AUD</span></div>`;
  return html`<svg class="chart" viewBox="0 0 320 160" role="img" aria-label=${label}>${lines}${bars}${dateTicks(
    rows.map((r) => r.day),
    x,
    hass,
  )}</svg>${legend}`;
}

/** Published gas meter reads joined by a line. */
export function gasChart(reads: GasRead[], hass: Hass) {
  if (reads.length < 2) return nothing;
  const values = reads.map((r) => r.index);
  const pad = Math.max(1, (Math.max(...values) - Math.min(...values)) * 0.1);
  const t = ticks(
    Math.min(...values) - pad,
    Math.max(...values) + pad,
    4,
    false,
  );
  const lo = t[0] ?? 0,
    hi = t.at(-1) ?? 1;
  const y = (v: number) =>
    BOTTOM - ((v - lo) / (hi - lo || 1)) * (BOTTOM - TOP);
  const first = Date.parse(reads[0]?.day ?? ""),
    last = Date.parse(reads.at(-1)?.day ?? "");
  const x = (i: number) =>
    LEFT +
    ((Date.parse(reads[i]?.day ?? "") - first) / (last - first || 1)) *
      (RIGHT - LEFT);
  const path = reads
    .map(
      (_, i) =>
        `${i ? "L" : "M"}${x(i).toFixed(1)},${y(values[i] ?? 0).toFixed(1)}`,
    )
    .join(" ");
  return html`<svg class="chart" viewBox="0 0 320 160" role="img" aria-label="Gas meter index at each published read, in cubic metres.">${t.map((v) => svg`<line class="grid" x1=${LEFT} x2=${RIGHT} y1=${y(v)} y2=${y(v)}/><text x=${LEFT - 4} y=${y(v) + 3} text-anchor="end">${format(v, hass)}</text>`)}<path class="gas-line" d=${path}/>${reads.map((r, i) => svg`<g><title>${dateLabel(r.day, hass)}: ${format(r.index, hass, "m³")} ${r.source ? ` (${r.source})` : ""}</title><circle class="gas-point" cx=${x(i)} cy=${y(r.index)} r="3.5"/></g>`)}${dateTicks(
    reads.map((r) => r.day),
    x,
    hass,
  )}</svg><div class="legend"><span class="gas">Meter read</span><span class="unit-label">m³</span></div>`;
}

/** One read per day (the highest index wins), in date order. */
export function gasReads(raw: unknown): GasRead[] {
  if (!Array.isArray(raw)) return [];
  const byDay = new Map<string, GasRead>();
  for (const row of raw) {
    if (!row || typeof row !== "object") continue;
    const r = row as Record<string, unknown>;
    const index = typeof r.read_index === "number" ? r.read_index : Number.NaN;
    const day = typeof r.date === "string" ? r.date.slice(0, 10) : "";
    if (!Number.isFinite(index) || !/^\d{4}-\d{2}-\d{2}$/.test(day)) continue;
    const source = typeof r.source === "string" ? r.source : undefined;
    const prior = byDay.get(day);
    if (!prior || index > prior.index) byDay.set(day, { day, index, source });
  }
  return [...byDay.values()].sort((a, b) => a.day.localeCompare(b.day));
}
