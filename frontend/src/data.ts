import { text } from "./strings";
import type { DayRow, Entity, Hass, Service, Statistics } from "./types";

export function number(value: unknown): number | undefined {
  if (typeof value !== "number" && typeof value !== "string") return;
  if (typeof value === "string" && !value.trim()) return;
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
}
export function value(entity?: Entity): number | undefined {
  return number(entity?.state);
}
export function day(value: unknown): string | undefined {
  if (typeof value !== "string") return;
  const match = /^(\d{4})[-/](\d{2})[-/](\d{2})(?:$|T| )/.exec(value);
  if (!match) return;
  const iso = `${match[1]}-${match[2]}-${match[3]}`;
  const d = new Date(`${iso}T12:00:00Z`);
  return Number.isFinite(d.getTime()) && d.toISOString().slice(0, 10) === iso
    ? iso
    : undefined;
}
export function today(hass: Hass, now = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: hass.config.time_zone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const part = (key: string) => parts.find((p) => p.type === key)?.value;
  return `${part("year")}-${part("month")}-${part("day")}`;
}
/** Convert a civil midnight in HA's zone to an explicit UTC instant (including DST). */
export function midnight(hass: Hass, date: string): string {
  const target = Date.parse(`${date}T00:00:00Z`);
  let instant = target;
  const fmt = new Intl.DateTimeFormat("en-CA", {
    timeZone: hass.config.time_zone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });
  for (let i = 0; i < 3; i++) {
    const parts = fmt.formatToParts(new Date(instant));
    const p = (key: string) => parts.find((v) => v.type === key)?.value;
    const civil = Date.parse(
      `${p("year")}-${p("month")}-${p("day")}T${p("hour")}:${p("minute")}:${p("second")}Z`,
    );
    instant += target - civil;
  }
  return new Date(instant).toISOString();
}
export function yesterday(hass: Hass, now = new Date()): string {
  const date = new Date(`${today(hass, now)}T12:00:00Z`);
  date.setUTCDate(date.getUTCDate() - 1);
  return date.toISOString().slice(0, 10);
}
export function dateLabel(raw: unknown, hass: Hass): string {
  const iso = day(raw);
  return iso
    ? new Intl.DateTimeFormat(hass.locale?.language ?? "en", {
        day: "numeric",
        month: "short",
        year: "numeric",
        timeZone: "UTC",
      }).format(new Date(`${iso}T12:00:00Z`))
    : text("noData");
}
export function timestampLabel(raw: unknown, hass: Hass): string {
  const date = typeof raw === "string" ? new Date(raw) : undefined;
  return date && Number.isFinite(date.getTime())
    ? new Intl.DateTimeFormat(hass.locale?.language ?? "en", {
        dateStyle: "medium",
        timeStyle: "short",
        timeZone: hass.config.time_zone,
      }).format(date)
    : text("noData");
}
export function latestLabel(
  raw: unknown,
  hass: Hass,
  now = new Date(),
): string {
  const iso = day(raw);
  return iso === yesterday(hass, now)
    ? text("yesterday", hass.locale?.language)
    : `${text("latest", hass.locale?.language)}: ${dateLabel(iso, hass)}`;
}
export function format(n: number, hass: Hass, unit?: string): string {
  const locales: Record<string, string> = {
    comma_decimal: "en-US",
    decimal_comma: "de-DE",
    space_comma: "fr-FR",
  };
  const locale =
    locales[hass.locale?.number_format ?? ""] ?? hass.locale?.language ?? "en";
  return (
    new Intl.NumberFormat(locale, {
      ...(unit === "AUD"
        ? {
            style: "currency",
            currency: "AUD",
            currencyDisplay: "narrowSymbol",
          }
        : {}),
      maximumFractionDigits: unit === "AUD" ? 2 : 3,
      minimumFractionDigits: unit === "AUD" ? 2 : 0,
      useGrouping: hass.locale?.number_format !== "none",
    }).format(Object.is(n, -0) ? 0 : n) +
    (unit && unit !== "AUD" ? ` ${unit}` : "")
  );
}
export function services(hass?: Hass): Service[] {
  const groups = new Map<string, Service>();
  for (const entity of Object.values(hass?.states ?? {})) {
    const a = entity.attributes;
    if (
      typeof a.globird_sensor_key !== "string" ||
      a.account_id == null ||
      a.account_service_id == null
    )
      continue;
    const accountId = String(a.account_id),
      id = String(a.account_service_id),
      key = `${accountId}:${id}`;
    const group = groups.get(key) ?? {
      id,
      accountId,
      type: String(a.service_type).toLowerCase().includes("gas")
        ? "gas"
        : "electricity",
      entities: {},
    };
    if (a.globird_sensor_key !== "register")
      group.entities[a.globird_sensor_key] = entity;
    groups.set(key, group);
  }
  return [...groups.values()].filter((s) => Object.keys(s.entities).length > 0);
}
export function globalEntities(hass: Hass, key: string): Entity[] {
  return Object.values(hass.states).filter(
    (e) => e.attributes.globird_sensor_key === key,
  );
}
export function rows(
  entity: Entity | undefined,
  attr: string,
  dateKey: string,
  valueKey: string,
): Map<string, number> {
  const result = new Map<string, number>();
  const source = entity?.attributes[attr];
  if (Array.isArray(source) && entity?.state !== "unavailable")
    for (const row of source) {
      if (!row || typeof row !== "object") continue;
      const d = day(row[dateKey]),
        n = number(row[valueKey]);
      if (d && n !== undefined) result.set(d, n);
    }
  return result;
}
export function history(service: Service, days = 7): DayRow[] {
  const usage = rows(
    service.entities.usage_total,
    "daily",
    "readDate",
    "usage",
  );
  const costs = rows(
    service.entities.cost_total,
    "daily_totals",
    "date",
    "amount",
  );
  const exports = rows(
    service.entities.solar_export_total,
    "daily",
    "readDate",
    "usage",
  );
  const controlled = rows(
    service.entities.controlled_load_total,
    "daily",
    "readDate",
    "usage",
  );
  const incomplete = new Set(
    (Array.isArray(service.entities.cost_total?.attributes.incomplete_days)
      ? service.entities.cost_total.attributes.incomplete_days
      : []
    ).map(day),
  );
  return [
    ...new Set([
      ...usage.keys(),
      ...costs.keys(),
      ...exports.keys(),
      ...controlled.keys(),
    ]),
  ]
    .sort()
    .slice(-days)
    .map((d) => ({
      day: d,
      usage: usage.get(d),
      export: exports.get(d),
      controlled: controlled.get(d),
      cost: incomplete.has(d) ? undefined : costs.get(d),
      incomplete: incomplete.has(d),
    }));
}
export function aligned(rows: DayRow[]): DayRow[] {
  return rows.filter(
    (r) => r.usage !== undefined && r.cost !== undefined && !r.incomplete,
  );
}
export function average(
  rows: DayRow[],
  key: "usage" | "export" | "controlled" | "cost",
): { value?: number; days: number } {
  const values = rows
    .map((r) => r[key])
    .filter((n): n is number => n !== undefined);
  return {
    value: values.length
      ? values.reduce((a, b) => a + b, 0) / values.length
      : undefined,
    days: values.length,
  };
}
export function statisticsRows(
  result: Statistics,
  service: Service,
  hass: Hass,
): DayRow[] {
  const map = new Map<string, DayRow>();
  for (const [metric, key] of [
    ["usage_total", "usage"],
    ["solar_export_total", "export"],
    ["controlled_load_total", "controlled"],
    ["cost_total", "cost"],
  ] as const) {
    const id = service.entities[metric]?.attributes.statistic_id;
    if (typeof id !== "string") continue;
    for (const row of result[id] ?? []) {
      const n = number(row.change);
      if (n === undefined) continue;
      const d = today(hass, new Date(row.start));
      const item = map.get(d) ?? { day: d };
      item[key] = n;
      map.set(d, item);
    }
  }
  const incomplete = new Set(
    history(service, 31)
      .filter((r) => r.incomplete)
      .map((r) => r.day),
  );
  return [...map.values()]
    .sort((a, b) => a.day.localeCompare(b.day))
    .map((r) =>
      incomplete.has(r.day) ? { ...r, cost: undefined, incomplete: true } : r,
    );
}
export function notices(hass: Hass, service: Service): string[] {
  const result: string[] = [];
  const status = service.entities.latest_data_status?.state;
  if (
    status === "waiting_for_cost" ||
    status === "waiting_for_usage" ||
    status === "no_data"
  )
    result.push(text(status, hass.locale?.language));
  if (history(service).some((r) => r.incomplete))
    result.push(text("incomplete", hass.locale?.language));
  // Global refresh diagnostics have no account metadata; report failures without exposing error payloads.
  for (const refresh of globalEntities(hass, "refresh_status"))
    if (refresh.state === "error") {
      const raw = refresh.attributes.last_successful_refresh;
      result.push(
        `${text("stale", hass.locale?.language)}${typeof raw === "string" ? ` Last successful refresh: ${timestampLabel(raw, hass)}.` : ""}`,
      );
    }
  return result;
}
