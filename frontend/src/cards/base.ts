import {
  html,
  LitElement,
  nothing,
  type PropertyValues,
  type TemplateResult,
} from "lit";
import { type ChartMode, dailyChart, gasChart, gasReads } from "../charts";
import {
  dateLabel,
  format,
  history,
  midnight,
  noticeItems,
  number,
  services,
  statisticsRows,
  today,
} from "../data";
import { text } from "../strings";
export type AlertTone = "info" | "warning" | "success";
const alertIcons: Record<AlertTone, string> = {
  info: "M11 9h2V7h-2m1 13c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8m0-18A10 10 0 0 0 2 12a10 10 0 0 0 10 10 10 10 0 0 0 10-10A10 10 0 0 0 12 2m-1 15h2v-6h-2z",
  warning: "M12 2 1 21h22M12 6l7.53 13H4.47M11 10v4h2v-4m-2 6v2h2v-2",
  success:
    "M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10 10-4.5 10-10S17.5 2 12 2m0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8m4.59-12.42L10 14.17l-2.59-2.58L6 13l4 4 8-8z",
};
/** A tinted, icon-led status message in the style of Home Assistant alerts. */
export function alert(message: unknown, tone: AlertTone = "info") {
  return html`<p class="alert ${tone}" role="status"><svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d=${alertIcons[tone]}/></svg><span>${message}</span></p>`;
}
/** The disclosure chevron of a details summary; it rotates when open. */
export const chevron = html`<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7.41 8.58 12 13.17l4.59-4.59L18 10l-6 6-6-6z"/></svg>`;

import { styles } from "../styles";
import type {
  CardConfig,
  DayRow,
  Entity,
  Hass,
  Service,
  Statistics,
} from "../types";

export abstract class GloBirdCard extends LitElement {
  static override styles = styles;
  static override properties = {
    hass: { attribute: false },
    config: { attribute: false },
    selected: { state: true },
    statRows: { state: true },
    historyError: { state: true },
    historyLoading: { state: true },
    chartMode: { state: true },
  };
  declare hass?: Hass;
  declare config: CardConfig;
  declare protected selected?: string;
  declare protected statRows?: DayRow[];
  declare protected historyError: boolean;
  declare protected historyLoading: boolean;
  declare protected chartMode: ChartMode;
  private historyKey = "";
  private serviceSelections: Partial<Record<Service["type"], string>> = {};
  private request = 0;
  static cardTitle = "GloBird";
  static iconPath = "M13 2 3 14h7l-1 8L21 9h-8l1-7z";
  static accountCard = false;
  constructor() {
    super();
    this.config = { type: "" };
    this.historyError = false;
    this.historyLoading = false;
    this.chartMode = "usage";
  }
  static getConfigElement() {
    return document.createElement("globird-card-editor");
  }
  static getStubConfig(hass: Hass): Partial<CardConfig> {
    if (this.accountCard) {
      const entities = Object.values(hass.states).filter(
        (e) => e.attributes.globird_sensor_key === "dashboard_balance",
      );
      return entities.length === 1 ? { entity: entities[0]?.entity_id } : {};
    }
    const list = services(hass).filter((s) => s.type === "electricity");
    return list.length === 1
      ? { entity: Object.values(list[0]?.entities ?? {})[0]?.entity_id }
      : {};
  }
  setConfig(config: CardConfig) {
    if (!config || typeof config.type !== "string")
      throw new Error("A card type is required.");
    if (
      config.entity !== undefined &&
      (typeof config.entity !== "string" ||
        !config.entity.startsWith("sensor."))
    )
      throw new Error("Select a sensor entity.");
    if (
      config.history_days !== undefined &&
      (!Number.isInteger(config.history_days) ||
        config.history_days < 1 ||
        config.history_days > 31)
    )
      throw new Error("History days must be 1–31.");
    if (
      config.history_source !== undefined &&
      !["attributes", "statistics"].includes(config.history_source)
    )
      throw new Error("Unknown history source.");
    if (
      config.default_service_type !== undefined &&
      !["gas", "electricity"].includes(config.default_service_type)
    )
      throw new Error("Unknown service type.");
    this.config = { ...config };
    this.selected = undefined;
    this.serviceSelections = {};
  }
  getCardSize() {
    return 4;
  }
  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: "auto" };
  }
  protected get service(): Service | undefined {
    const all = services(this.hass);
    const anchor = this.config.entity
      ? all.find((s) =>
          Object.values(s.entities).some(
            (e) => e.entity_id === this.config.entity,
          ),
        )
      : undefined;
    if (this.config.entity && !anchor) return undefined;
    if (anchor) {
      const defaults = all.filter(
        (s) =>
          s.accountId === anchor.accountId &&
          s.type === this.config.default_service_type,
      );
      const initial =
        this.config.default_service_type && defaults.length === 1
          ? defaults[0]
          : anchor;
      return (
        all.find(
          (s) => s.accountId === anchor.accountId && s.id === this.selected,
        ) ?? initial
      );
    }
    const accounts = new Set(all.map((s) => s.accountId));
    if (accounts.size !== 1) return undefined;
    const typed = all.filter(
      (s) => s.type === (this.config.default_service_type ?? "electricity"),
    );
    return (
      all.find((s) => s.id === this.selected) ??
      (typed.length === 1 ? typed[0] : undefined)
    );
  }
  protected override shouldUpdate(changed: PropertyValues<this>) {
    if (changed.size !== 1 || !changed.has("hass")) return true;
    const old = changed.get("hass");
    if (
      !old ||
      !this.hass ||
      old.locale !== this.hass.locale ||
      old.config !== this.hass.config
    )
      return true;
    const relevant = (h: Hass) =>
      Object.values(h.states).filter(
        (e) => typeof e.attributes.globird_sensor_key === "string",
      );
    const before = relevant(old),
      after = relevant(this.hass);
    return (
      before.length !== after.length ||
      after.some((e) => old.states[e.entity_id] !== e)
    );
  }
  protected override updated() {
    void this.loadHistory();
  }
  private async loadHistory() {
    const service = this.service,
      hass = this.hass;
    if (
      !service ||
      !hass ||
      this.config.history_source !== "statistics" ||
      service.type !== "electricity"
    ) {
      this.historyKey = "";
      this.request++;
      this.statRows = undefined;
      this.historyLoading = false;
      this.historyError = false;
      return;
    }
    const ids = [
      "usage_total",
      "solar_export_total",
      "controlled_load_total",
      "cost_total",
    ]
      .map((k) => service.entities[k]?.attributes.statistic_id)
      .filter((v): v is string => typeof v === "string");
    const days = this.config.history_days ?? 7;
    const refreshed = Object.values(hass.states)
      .filter(
        (e) => e.attributes.globird_sensor_key === "last_successful_refresh",
      )
      .map((e) => e.state)
      .join();
    const key = JSON.stringify([
      service.accountId,
      service.id,
      ids,
      days,
      today(hass),
      refreshed,
    ]);
    if (key === this.historyKey) return;
    this.historyKey = key;
    const request = ++this.request;
    this.statRows = undefined;
    this.historyError = false;
    if (!ids.length || !hass.callWS) {
      this.historyError = true;
      return;
    }
    this.historyLoading = true;
    const start = new Date(`${today(hass)}T12:00:00Z`);
    start.setUTCDate(start.getUTCDate() - days);
    try {
      const result = await hass.callWS<Statistics>({
        type: "recorder/statistics_during_period",
        start_time: midnight(hass, start.toISOString().slice(0, 10)),
        end_time: midnight(hass, today(hass)),
        statistic_ids: ids,
        period: "day",
        types: ["change"],
      });
      if (request === this.request)
        this.statRows = statisticsRows(result, service, hass)
          .filter((r) => r.day < today(hass))
          .slice(-days);
    } catch {
      if (request === this.request) this.historyError = true;
    } finally {
      if (request === this.request) this.historyLoading = false;
    }
  }
  protected get days(): DayRow[] {
    return (
      this.statRows ??
      (this.service
        ? history(this.service, Math.min(this.config.history_days ?? 7, 7))
        : [])
    );
  }
  protected metric(
    label: string,
    entity?: Entity,
    options: { n?: number; unit?: string; note?: string } = {},
  ) {
    const n = "n" in options ? options.n : number(entity?.state);
    const unit =
      options.unit ??
      (typeof entity?.attributes.unit_of_measurement === "string"
        ? entity.attributes.unit_of_measurement
        : undefined);
    const missing = entity?.state === "unavailable" || n === undefined;
    const display =
      entity?.state === "unavailable"
        ? text("unavailable")
        : n === undefined
          ? text("noData")
          : html`${format(n, this.hass as Hass, unit === "AUD" ? unit : undefined)}${unit && unit !== "AUD" ? html`<span class="unit"> ${unit}</span>` : nothing}`;
    return html`<button class="metric" type="button" ?disabled=${!entity} @click=${() => entity && this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId: entity.entity_id }, bubbles: true, composed: true }))}><span class="label">${label}</span><span class="value ${missing ? "muted" : ""}">${display}</span>${n !== undefined && n < 0 && unit === "AUD" ? html`<small>Credit</small>` : nothing}${options.note ? html`<small>${options.note}</small>` : nothing}</button>`;
  }
  private selector() {
    const active = this.service;
    if (!active) return nothing;
    const same = services(this.hass).filter(
      (s) => s.accountId === active.accountId,
    );
    if (
      !same.some((s) => s.type === "gas") ||
      !same.some((s) => s.type === "electricity")
    )
      return nothing;
    return html`<fieldset><legend>Energy service</legend>${(
      ["electricity", "gas"] as const
    ).map((type) => {
      const candidates = same.filter((s) => s.type === type);
      const remembered =
        candidates.find((s) => s.id === this.serviceSelections[type]) ??
        candidates.find((s) =>
          Object.values(s.entities).some(
            (e) => e.entity_id === this.config.entity,
          ),
        );
      const target =
        active.type === type
          ? active
          : (remembered ??
            (candidates.length === 1 ? candidates[0] : undefined));
      return html`<label class="choice"><input type="radio" name="energy-service" value=${type} .checked=${active.type === type} ?disabled=${!target} @change=${() => {
        if (target) {
          this.serviceSelections[active.type] = active.id;
          this.serviceSelections[type] = target.id;
          this.selected = target.id;
        }
      }}>${text(type)}</label>`;
    })}</fieldset>${(["electricity", "gas"] as const).map((type) => {
      const candidates = same.filter((s) => s.type === type);
      if (candidates.length < 2) return nothing;
      return html`<label class="service-picker">${text(type)} service<select aria-label=${`${text(type)} service`} .value=${active.type === type ? active.id : (this.serviceSelections[type] ?? "")} @change=${(
        event: Event,
      ) => {
        const id = (event.target as HTMLSelectElement).value;
        if (candidates.some((s) => s.id === id)) {
          this.serviceSelections[active.type] = active.id;
          this.serviceSelections[type] = id;
          this.selected = id;
        }
      }}><option value="">Select a service</option>${candidates.map((s, i) => html`<option value=${s.id} .selected=${(active.type === type ? active.id : this.serviceSelections[type]) === s.id}>${text(type)} service ${i + 1}</option>`)}</select></label>`;
    })}`;
  }
  protected gasReading() {
    const e = this.service?.entities.latest_gas_reading,
      h = this.hass as Hass;
    const reads = gasReads(e?.attributes.history);
    const latest = reads.at(-1),
      previous = reads.at(-2);
    const used =
      latest && previous && latest.index >= previous.index
        ? latest.index - previous.index
        : undefined;
    return html`<div class="metrics">${this.metric("Gas meter reading", e, { note: e ? dateLabel(e.attributes.latest_reading_date, h) : undefined })}${this.metric("Used between reads", reads.length > 1 ? e : undefined, { n: used, unit: "m³", note: previous && latest ? `${dateLabel(previous.day, h)} – ${dateLabel(latest.day, h)}` : "Needs two meter reads" })}</div>${gasChart(reads, h)}<p class="subtitle">Meter index (m³), not daily consumption. Gas meters are read about every three months.</p>`;
  }
  protected chart(rows: DayRow[]) {
    const h = this.hass as Hass;
    if (!rows.some((r) => r.usage !== undefined || r.export !== undefined))
      return html`<p class="subtitle">No daily readings available.</p>`;
    const mode = this.chartMode;
    const available = rows.filter(
      (r) => r.usage !== undefined || r.export !== undefined,
    );
    return html`<fieldset class="chart-mode"><legend>Chart</legend>${(
      [
        ["usage", "Usage (kWh)"],
        ["cost", "Cost ($)"],
      ] as const
    ).map(
      ([value, label]) =>
        html`<label class="choice"><input type="radio" name="chart-mode" value=${value} .checked=${mode === value} @change=${() => {
          this.chartMode = value;
        }}>${label}</label>`,
    )}</fieldset>${dailyChart(rows, mode, h)}<details><summary>Daily readings${chevron}</summary><table><caption>${available.length} days with available readings. Missing values are not zero.</caption><thead><tr><th scope="col">Date</th><th scope="col">Import (kWh)</th><th scope="col">Export (kWh)</th><th scope="col">Cost (AUD)</th></tr></thead><tbody>${rows.map((r) => html`<tr><th scope="row">${dateLabel(r.day, h)}</th><td>${r.usage === undefined ? "—" : format(r.usage, h)}</td><td>${r.export === undefined ? "—" : format(r.export, h)}</td><td>${r.incomplete ? "Incomplete" : r.cost === undefined ? "—" : format(r.cost, h, "AUD")}</td></tr>`)}</tbody></table></details>`;
  }
  protected abstract content(): TemplateResult;
  protected override render() {
    const cardClass = this.constructor as typeof GloBirdCard;
    const service = this.service;
    const ready = this.hass && (cardClass.accountCard || service);
    return html`<ha-card><header><span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path fill="currentColor" d=${cardClass.iconPath}/></svg></span><div><h2>${this.config.title || cardClass.cardTitle}</h2><p class="subtitle">GloBird Energy${service ? ` · ${text(service.type)}` : ""}</p></div></header><div class="body">${ready ? html`${cardClass.accountCard ? nothing : this.selector()}${this.content()}${service ? noticeItems(this.hass as Hass, service).map((n) => alert(n.text, n.tone)) : nothing}${this.historyLoading ? html`<p class="subtitle" role="status">Loading daily statistics…</p>` : nothing}${this.historyError ? alert(text("historyError"), "warning") : nothing}` : html`<p class="empty" role="status">${!this.hass || !Object.values(this.hass.states).some((e) => e.attributes.globird_sensor_key) ? text("loading") : text("choose")}</p>`}</div></ha-card>`;
  }
}
