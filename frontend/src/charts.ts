import { html, nothing, type SVGTemplateResult, svg } from "lit";
import { dateLabel, format, day as parseDay } from "./data";
import type { DayRow, Hass, Series } from "./types";

export type ChartMode = "usage" | "cost";
export interface GasRead {
  day: string;
  index: number;
  source?: string;
}
export interface ChartOptions {
  registers?: Series[];
  categories?: Series[];
  temperature?: boolean;
}

// Plot area of the 320 × 160 viewBox; labels sit outside it.
const LEFT = 36,
  TOP = 8,
  BOTTOM = 136;
const right = (temperature: boolean) => (temperature ? 290 : 312);

const IMPORT = "var(--energy-grid-consumption-color, #488fc2)";
const EXPORT = "var(--energy-grid-return-color, #8353d1)";
const CARD = "var(--card-background-color, #fff)";
// Shades of one series colour, so every import register still reads as
// import and every export register as export.
const shade = (color: string, i: number) =>
  i === 0
    ? color
    : `color-mix(in srgb, ${color} ${[100, 70, 48, 34][Math.min(i, 3)]}%, #fff)`;
const CATEGORY_COLORS: Record<string, string> = {
  SUPPLY: IMPORT,
  USAGE: `color-mix(in srgb, ${IMPORT} 50%, #fff)`,
  SOLAR: EXPORT,
  "ZEROHERO CREDIT":
    "var(--ha-color-fill-success-loud-resting, var(--success-color, #43a047))",
  "SUPER EXPORT TOP UP": "var(--amber-color, #ffc107)",
};
const TRACKING_COLORS = [
  "var(--amber-color, #ffc107)",
  "var(--orange-color, #ff9800)",
];
const NEUTRAL = ["#8d6e63", "#78909c", "#a1887f", "#90a4ae"];

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

function scale(t: number[]) {
  const lo = t[0] ?? 0,
    hi = t.at(-1) ?? 1;
  return (v: number) => BOTTOM - ((v - lo) / (hi - lo || 1)) * (BOTTOM - TOP);
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

/** A line through the days that have a value; gaps break the line. */
function linePath(points: (number | undefined)[], x: (i: number) => number) {
  let path = "",
    pen = false;
  points.forEach((y, i) => {
    if (y === undefined) {
      pen = false;
      return;
    }
    path += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y.toFixed(1)} `;
    pen = true;
  });
  return path.trim();
}

function swatch(label: string, color: string, kind = "") {
  return html`<span class=${kind} style=${`--legend-color: ${color}`}>${label}</span>`;
}

interface Segment {
  label: string;
  value: number;
  color: string;
}

/** Daily bars around a zero line. Usage stacks the import registers above
 * zero and the export registers below; cost stacks charges above and credits
 * below. Tracking registers, which re-report energy already in a bar, are
 * markers rather than stacked segments. Missing days leave a gap, never a
 * zero bar. Daily temperatures can be drawn against a second axis. */
export function dailyChart(
  rows: DayRow[],
  mode: ChartMode,
  hass: Hass,
  options: ChartOptions = {},
) {
  // Temperatures explain usage; the portal also leaves them off the cost view.
  const temperature =
    mode === "usage" &&
    options.temperature !== false &&
    rows.some((r) => r.tempMax !== undefined || r.tempMin !== undefined);
  const RIGHT = right(temperature);
  const registers = options.registers ?? [];
  const stackedImport = registers.filter(
    (s) => s.direction === "import" && !s.tracking,
  );
  const stackedExport = registers.filter(
    (s) => s.direction === "export" && !s.tracking,
  );
  const tracking = registers.filter((s) => s.tracking);
  const categories = options.categories ?? [];
  const colorOf = new Map<string, string>();
  stackedImport.forEach((s, i) => {
    colorOf.set(s.key, shade(IMPORT, i));
  });
  stackedExport.forEach((s, i) => {
    colorOf.set(s.key, shade(EXPORT, i));
  });
  tracking.forEach((s, i) => {
    colorOf.set(
      s.key,
      TRACKING_COLORS[i % TRACKING_COLORS.length] ?? TRACKING_COLORS[0] ?? "",
    );
  });
  categories.forEach((s, i) => {
    colorOf.set(
      s.key,
      CATEGORY_COLORS[s.key.toUpperCase()] ?? NEUTRAL[i % NEUTRAL.length] ?? "",
    );
  });

  // Each day's segments above and below zero.
  const days = rows.map((r) => {
    const up: Segment[] = [],
      down: Segment[] = [];
    if (mode === "cost") {
      if (r.incomplete) return { up, down };
      const parts = categories.filter(
        (s) => r.categories?.[s.key] !== undefined,
      );
      if (parts.length)
        for (const s of parts) {
          const value = r.categories?.[s.key] ?? 0;
          (value < 0 ? down : up).push({
            label: s.label,
            value,
            color: colorOf.get(s.key) ?? IMPORT,
          });
        }
      else if (r.cost !== undefined)
        (r.cost < 0 ? down : up).push({
          label: r.cost < 0 ? "Credit" : "Net cost",
          value: r.cost,
          color:
            r.cost < 0 ? (CATEGORY_COLORS["ZEROHERO CREDIT"] ?? "") : IMPORT,
        });
      return { up, down };
    }
    const importParts = stackedImport.filter(
      (s) => r.registers?.[s.key] !== undefined,
    );
    if (importParts.length)
      for (const s of importParts)
        up.push({
          label: s.label,
          value: r.registers?.[s.key] ?? 0,
          color: colorOf.get(s.key) ?? IMPORT,
        });
    else if (r.usage !== undefined)
      up.push({ label: "Grid import", value: r.usage, color: IMPORT });
    if (r.controlled !== undefined)
      up.push({
        label: "Controlled load",
        value: r.controlled,
        color: "var(--energy-non-fossil-color, #0f9d58)",
      });
    const exportParts = stackedExport.filter(
      (s) => r.registers?.[s.key] !== undefined,
    );
    if (exportParts.length)
      for (const s of exportParts)
        down.push({
          label: s.label,
          value: -(r.registers?.[s.key] ?? 0),
          color: colorOf.get(s.key) ?? EXPORT,
        });
    else if (r.export !== undefined)
      down.push({ label: "Solar export", value: -r.export, color: EXPORT });
    return { up, down };
  });
  const sum = (list: Segment[]) => list.reduce((a, s) => a + s.value, 0);
  const values = days.flatMap((d) => [sum(d.up), sum(d.down)]);
  const t = ticks(Math.min(0, ...values), Math.max(0, ...values));
  const y = scale(t);
  const unit = mode === "cost" ? "AUD" : "kWh";
  const slot = (RIGHT - LEFT) / Math.max(rows.length, 1);
  const width = Math.max(2, Math.min(slot * 0.7, 14));
  const x = (i: number) => LEFT + slot * i + slot / 2;
  const rect = (i: number, from: number, to: number, color: string) =>
    svg`<rect x=${x(i) - width / 2} y=${Math.min(y(from), y(to))} width=${width} height=${Math.max(0, Math.abs(y(to) - y(from)))} style=${`fill: ${color}`}/>`;

  const bars = rows.map((r, i) => {
    const { up, down } = days[i] ?? { up: [], down: [] };
    const parts: SVGTemplateResult[] = [];
    for (const list of [up, down]) {
      let base = 0;
      for (const s of list) {
        parts.push(rect(i, base, base + s.value, s.color));
        base += s.value;
      }
    }
    const marks =
      mode === "usage"
        ? tracking
            .filter((s) => (r.registers?.[s.key] ?? 0) !== 0)
            .map((s) => {
              const v =
                (r.registers?.[s.key] ?? 0) *
                (s.direction === "export" ? -1 : 1);
              return svg`<circle class="marker" cx=${x(i)} cy=${y(v)} r="2" style=${`fill: ${colorOf.get(s.key)}`}/>`;
            })
        : [];
    const shown = [...up, ...down].map(
      (s) => `${s.label} ${format(Math.abs(s.value), hass, unit)}`,
    );
    const tracked =
      mode === "usage"
        ? tracking
            .filter((s) => (r.registers?.[s.key] ?? 0) !== 0)
            .map(
              (s) =>
                `${s.label} ${format(r.registers?.[s.key] ?? 0, hass, "kWh")} (already counted)`,
            )
        : [];
    const temps =
      temperature && (r.tempMin !== undefined || r.tempMax !== undefined)
        ? [
            `${r.tempMin === undefined ? "–" : format(r.tempMin, hass)}–${r.tempMax === undefined ? "–" : format(r.tempMax, hass)} °C`,
          ]
        : [];
    const tip =
      mode === "cost" && r.incomplete
        ? "cost incomplete"
        : [...shown, ...tracked, ...temps].join("; ") || "no data";
    return svg`<g><title>${dateLabel(r.day, hass)}: ${tip}</title><rect class="hit" x=${x(i) - slot / 2} y=${TOP} width=${slot} height=${BOTTOM - TOP}/>${parts}${marks}</g>`;
  });

  let tempLayer: unknown = nothing;
  if (temperature) {
    const temps = rows.flatMap((r) =>
      [r.tempMin, r.tempMax].filter((v): v is number => v !== undefined),
    );
    const tt = ticks(Math.min(...temps) - 1, Math.max(...temps) + 1, 3, false);
    const ty = scale(tt);
    tempLayer = svg`${tt.map((v) => svg`<text x=${RIGHT + 4} y=${ty(v) + 3}>${format(v, hass)}°</text>`)}<path class="temp max" d=${linePath(
      rows.map((r) => (r.tempMax === undefined ? undefined : ty(r.tempMax))),
      x,
    )}/><path class="temp min" d=${linePath(
      rows.map((r) => (r.tempMin === undefined ? undefined : ty(r.tempMin))),
      x,
    )}/>`;
  }

  const legendSeries: unknown[] = [];
  const seen = new Set<string>();
  for (const d of days)
    for (const s of [...d.up, ...d.down])
      if (!seen.has(s.label)) {
        seen.add(s.label);
        legendSeries.push(swatch(s.label, s.color));
      }
  if (mode === "usage")
    for (const s of tracking)
      if (rows.some((r) => (r.registers?.[s.key] ?? 0) !== 0))
        legendSeries.push(
          swatch(
            `${s.label} (already counted)`,
            colorOf.get(s.key) ?? "",
            "dot",
          ),
        );
  if (temperature)
    legendSeries.push(
      swatch("Max temp", "var(--state-climate-heat-color, #ff8100)", "line"),
      swatch("Min temp", "var(--state-climate-cool-color, #2b9af9)", "line"),
    );
  const label =
    mode === "usage"
      ? "Daily grid import above the zero line and solar export below it, in kilowatt-hours, split by register where available. Values are listed in the daily readings table."
      : "Daily charges above the zero line and credits below it, in Australian dollars, split by charge category where available. Values are listed in the daily readings table.";
  return html`<svg class="chart" viewBox="0 0 320 160" role="img" aria-label=${label}>${t.map((v) => svg`<line class=${v === 0 ? "zero" : "grid"} x1=${LEFT} x2=${RIGHT} y1=${y(v)} y2=${y(v)}/><text x=${LEFT - 4} y=${y(v) + 3} text-anchor="end">${mode === "cost" ? `$${format(v, hass)}` : format(v, hass)}</text>`)}${bars}${tempLayer}${dateTicks(
    rows.map((r) => r.day),
    x,
    hass,
  )}</svg><div class="legend">${legendSeries}<span class="unit-label">${mode === "cost" ? "AUD" : "kWh"}${temperature ? " · °C" : ""}</span></div>`;
}

const GAS = "var(--energy-gas-color, #8e021b)";
/** Friendly names for the portal's read sources. */
function sourceLabel(source: string | undefined) {
  if (!source) return "Meter reads";
  if (/invoice/i.test(source)) return "Invoice reads";
  if (/distributor|self/i.test(source)) return "Distributor and self reads";
  return source;
}

/** Gas meter reads, one line per read source (invoice reads, distributor and
 * self reads), on a shared date axis. */
export function gasChart(raw: unknown, hass: Hass) {
  const series = gasSeries(raw);
  const all = [...series.values()].flat();
  if (new Set(all.map((r) => r.day)).size < 2) return nothing;
  const values = all.map((r) => r.index);
  const pad = Math.max(1, (Math.max(...values) - Math.min(...values)) * 0.1);
  const t = ticks(
    Math.min(...values) - pad,
    Math.max(...values) + pad,
    4,
    false,
  );
  const y = scale(t);
  const RIGHT = right(false);
  const times = all.map((r) => Date.parse(r.day));
  const first = Math.min(...times),
    last = Math.max(...times);
  const xOf = (iso: string) =>
    LEFT + ((Date.parse(iso) - first) / (last - first || 1)) * (RIGHT - LEFT);
  const sorted = [...new Set(all.map((r) => r.day))].sort();
  const lines = [...series.entries()].map(([source, reads], k) => {
    const color = k === 0 ? GAS : `color-mix(in srgb, ${GAS} 55%, ${CARD})`;
    const path = reads
      .map(
        (r, i) =>
          `${i ? "L" : "M"}${xOf(r.day).toFixed(1)},${y(r.index).toFixed(1)}`,
      )
      .join(" ");
    return {
      label: sourceLabel(source),
      color,
      dashed: k > 0,
      layer: svg`<path class=${k > 0 ? "gas-line dashed" : "gas-line"} d=${path} style=${`stroke: ${color}`}/>${reads.map((r) => svg`<g><title>${dateLabel(r.day, hass)}: ${format(r.index, hass, "m³")} (${sourceLabel(source)})</title>${k > 0 ? svg`<rect class="gas-point" x=${xOf(r.day) - 3} y=${y(r.index) - 3} width="6" height="6" style=${`stroke: ${color}`}/>` : svg`<circle class="gas-point" cx=${xOf(r.day)} cy=${y(r.index)} r="3.5" style=${`stroke: ${color}`}/>`}</g>`)}`,
    };
  });
  return html`<svg class="chart" viewBox="0 0 320 160" role="img" aria-label="Gas meter index at each published read, in cubic metres, by read source.">${t.map((v) => svg`<line class="grid" x1=${LEFT} x2=${RIGHT} y1=${y(v)} y2=${y(v)}/><text x=${LEFT - 4} y=${y(v) + 3} text-anchor="end">${format(v, hass)}</text>`)}${lines.map((l) => l.layer)}${dateTicks(sorted, (i) => xOf(sorted[i] ?? ""), hass)}</svg><div class="legend">${lines.map((l) => swatch(l.label, l.color, l.dashed ? "line dashed" : "point"))}<span class="unit-label">m³</span></div>`;
}

function readRows(raw: unknown): GasRead[] {
  if (!Array.isArray(raw)) return [];
  const result: GasRead[] = [];
  for (const row of raw) {
    if (!row || typeof row !== "object") continue;
    const r = row as Record<string, unknown>;
    const index = typeof r.read_index === "number" ? r.read_index : Number.NaN;
    const day = parseDay(r.date);
    if (!Number.isFinite(index) || day === undefined) continue;
    const source = typeof r.source === "string" ? r.source : undefined;
    result.push({ day, index, source });
  }
  return result;
}

/** Reads grouped by source, one per day and source, in date order. */
export function gasSeries(raw: unknown): Map<string | undefined, GasRead[]> {
  const series = new Map<string | undefined, Map<string, GasRead>>();
  for (const read of readRows(raw)) {
    const byDay = series.get(read.source) ?? new Map<string, GasRead>();
    const prior = byDay.get(read.day);
    if (!prior || read.index > prior.index) byDay.set(read.day, read);
    series.set(read.source, byDay);
  }
  return new Map(
    [...series.entries()]
      // Invoice reads first: they are the reads bills use.
      .sort(
        ([a], [b]) =>
          Number(!/invoice/i.test(a ?? "")) - Number(!/invoice/i.test(b ?? "")),
      )
      .map(([source, byDay]) => [
        source,
        [...byDay.values()].sort((a, b) => a.day.localeCompare(b.day)),
      ]),
  );
}

/** One read per day (the highest index wins), in date order. */
export function gasReads(raw: unknown): GasRead[] {
  const byDay = new Map<string, GasRead>();
  for (const read of readRows(raw)) {
    const prior = byDay.get(read.day);
    if (!prior || read.index > prior.index) byDay.set(read.day, read);
  }
  return [...byDay.values()].sort((a, b) => a.day.localeCompare(b.day));
}
