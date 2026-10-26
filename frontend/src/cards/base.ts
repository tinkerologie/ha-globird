import {
  html,
  LitElement,
  nothing,
  type PropertyValues,
  svg,
  type TemplateResult,
} from "lit";
import {
  dateLabel,
  format,
  history,
  midnight,
  notices,
  number,
  services,
  statisticsRows,
  today,
} from "../data";
import { text } from "../strings";
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
  };
  declare hass?: Hass;
  declare config: CardConfig;
  declare protected selected?: string;
  declare protected statRows?: DayRow[];
  declare protected historyError: boolean;
  declare protected historyLoading: boolean;
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
    const display =
      entity?.state === "unavailable"
        ? text("unavailable")
        : n === undefined
          ? text("noData")
          : html`${format(n, this.hass as Hass, unit === "AUD" ? unit : undefined)}${unit && unit !== "AUD" ? html`<span class="unit"> ${unit}</span>` : nothing}`;
    return html`<button class="metric" type="button" ?disabled=${!entity} @click=${() => entity && this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId: entity.entity_id }, bubbles: true, composed: true }))}><span class="label">${label}</span><span class="value">${display}</span>${n !== undefined && n < 0 && unit === "AUD" ? html`<small>Credit</small>` : nothing}${options.note ? html`<small>${options.note}</small>` : nothing}</button>`;
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
    const e = this.service?.entities.latest_gas_reading;
    return html`<div class="metrics">${this.metric("Gas meter reading", e, { note: e ? dateLabel(e.attributes.latest_reading_date, this.hass as Hass) : undefined })}</div><p class="subtitle">Meter index (m³), not daily consumption. Actual readings may arrive only when the meter is read.</p>`;
  }
  protected chart(rows: DayRow[]) {
    const available = rows.filter(
      (r) => r.usage !== undefined || r.export !== undefined,
    );
    if (!available.length)
      return html`<p class="subtitle">No daily readings available.</p>`;
    const max = Math.max(
      1,
      ...available.flatMap((r) => [r.usage ?? 0, r.export ?? 0]),
    );
    const w = 300 / available.length;
    return html`<svg class="chart" viewBox="0 0 320 140" role="img" aria-label="Daily general import and solar export, in kilowatt-hours. Values are available in the daily readings table.">${available.map((r, i) => svg`<g><title>${r.day}: import ${r.usage ?? "no data"} kWh; export ${r.export ?? "no data"} kWh</title>${r.usage === undefined ? nothing : svg`<rect class="import" x=${10 + i * w} y=${115 - (r.usage / max) * 100} width=${Math.max(2, w * 0.32)} height=${Math.max(0, (r.usage / max) * 100)} rx="2"/>`}${r.export === undefined ? nothing : svg`<rect class="export" x=${10 + i * w + w * 0.36} y=${115 - (r.export / max) * 100} width=${Math.max(2, w * 0.32)} height=${Math.max(0, (r.export / max) * 100)} rx="2"/>`}</g>`)}<text x="10" y="136">${dateLabel(available[0]?.day, this.hass as Hass)}</text><text x="310" y="136" text-anchor="end">${dateLabel(available.at(-1)?.day, this.hass as Hass)}</text></svg><div class="legend"><span>General import</span><span>Solar export</span></div><details><summary>Daily readings</summary><table><caption>${available.length} days with available readings. Missing values are not zero.</caption><thead><tr><th scope="col">Date</th><th scope="col">Import</th><th scope="col">Export</th><th scope="col">Cost</th></tr></thead><tbody>${rows.map((r) => html`<tr><th scope="row">${dateLabel(r.day, this.hass as Hass)}</th><td>${r.usage === undefined ? "—" : format(r.usage, this.hass as Hass)}</td><td>${r.export === undefined ? "—" : format(r.export, this.hass as Hass)}</td><td>${r.incomplete ? "Incomplete" : r.cost === undefined ? "—" : format(r.cost, this.hass as Hass, "AUD")}</td></tr>`)}</tbody></table></details>`;
  }
  protected abstract content(): TemplateResult;
  protected override render() {
    const cardClass = this.constructor as typeof GloBirdCard;
    const service = this.service;
    const ready = this.hass && (cardClass.accountCard || service);
    return html`<ha-card><header><span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path fill="currentColor" d=${cardClass.iconPath}/></svg></span><div><h2>${this.config.title || cardClass.cardTitle}</h2><p class="subtitle">GloBird Energy${service ? ` · ${text(service.type)}` : ""}</p></div></header><div class="body">${ready ? html`${cardClass.accountCard ? nothing : this.selector()}${this.content()}${service ? notices(this.hass as Hass, service).map((n) => html`<p class="notice" role="status">${n}</p>`) : nothing}${this.historyLoading ? html`<p class="subtitle" role="status">Loading daily statistics…</p>` : nothing}${this.historyError ? html`<p class="notice" role="status">${text("historyError")}</p>` : nothing}` : html`<p class="empty" role="status">${!this.hass || !Object.values(this.hass.states).some((e) => e.attributes.globird_sensor_key) ? text("loading") : text("choose")}</p>`}</div></ha-card>`;
  }
}
