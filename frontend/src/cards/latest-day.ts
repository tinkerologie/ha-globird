import { html } from "lit";
import { dateLabel, day, latestLabel, number } from "../data";
import type { Hass } from "../types";
import { chevron, GloBirdCard } from "./base";
export class LatestDayCard extends GloBirdCard {
  static override cardTitle = "Latest day usage";
  static override iconPath =
    "M5 2h2v3h10V2h2v3h3v17H2V5h3V2m-1 8v10h16V10H4m3 3h4v4H7v-4";
  protected override content() {
    if (this.service?.type === "gas") return this.gasReading();
    const e = this.service?.entities ?? {},
      h = this.hass as Hass;
    const d = day(e.latest_day_usage?.attributes.latest_day);
    const u = number(e.latest_day_usage?.state);
    const exportEntity =
      d !== undefined &&
      day(e.latest_day_solar_export?.attributes.latest_day) === d
        ? e.latest_day_solar_export
        : undefined;
    const exported = number(exportEntity?.state);
    const cost =
      d !== undefined &&
      e.latest_day_cost &&
      day(e.latest_day_cost.attributes.latest_day) === d
        ? e.latest_day_cost
        : undefined;
    const controlled =
      d !== undefined &&
      day(e.latest_day_controlled_load?.attributes.latest_day) === d
        ? e.latest_day_controlled_load
        : undefined;
    return html`<p class="subtitle">${latestLabel(d, h)}</p><div class="metrics">${this.metric("Net cost", cost, { unit: "AUD", note: cost ? undefined : "Waiting for matching complete cost data" })}${this.metric("Net grid usage", undefined, { n: u !== undefined && exported !== undefined ? u - exported : undefined, unit: "kWh", note: "General import − solar export" })}${this.metric("General import", e.latest_day_usage)}${this.metric("Solar export", exportEntity)}${e.latest_day_controlled_load ? this.metric("Controlled load (separate)", controlled) : ""}</div><details><summary>About these readings${chevron}</summary><p>Negative net grid usage means more energy was exported than imported. Controlled load is shown separately. Costs and usage are paired only when their dates match.</p><p>Latest complete cost day: ${dateLabel(e.latest_day_cost?.attributes.latest_day, h)}. Readings may arrive 24–48 hours later.</p></details>`;
  }
}
