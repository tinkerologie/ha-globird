import { html } from "lit";
import { aligned, average, dateLabel, format, number } from "../data";
import type { Hass } from "../types";
import { GloBirdCard } from "./base";
export class ElectricityUsageCard extends GloBirdCard {
  static override cardTitle = "Electricity usage";
  override getCardSize() {
    return 7;
  }
  protected override content() {
    if (this.service?.type === "gas") return this.gasReading();
    const e = this.service?.entities ?? {},
      h = this.hass as Hass,
      rows = this.days;
    const avg = average(rows, "usage"),
      exp = average(rows, "export"),
      cost = average(aligned(rows), "cost");
    return html`<div class="metrics">${this.metric("General grid import", e.usage_total, { note: `${number(e.usage_total?.attributes.days) ?? 0} days of recent data` })}${this.metric("Solar export", e.solar_export_total, { note: `Through ${dateLabel(e.solar_export_total?.attributes.latest_day, h)}` })}${e.controlled_load_total ? this.metric("Controlled load (separate)", e.controlled_load_total) : ""}${this.metric("Average import per day", e.usage_total, { n: avg.value, unit: "kWh", note: `${avg.days} days with readings in the chart` })}${this.metric("Average export per day", e.solar_export_total, { n: exp.value, unit: "kWh", note: `${exp.days} days with readings in the chart` })}</div><p class="subtitle">${cost.value === undefined ? "No complete usage/cost comparison yet." : `Average net cost: ${format(cost.value, h, "AUD")} per day · ${cost.days} matching complete days.`}</p>${this.chart(rows)}<p class="subtitle">${this.statRows ? "Recorder statistics" : "Recent attribute history (up to 7 days)"}. General import and controlled load remain separate.</p>`;
  }
}
