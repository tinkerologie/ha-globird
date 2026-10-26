import { html } from "lit";
import { dateLabel, globalEntities, number, timestampLabel } from "../data";
import type { Hass } from "../types";
import { GloBirdCard } from "./base";
export class AccountCard extends GloBirdCard {
  static override cardTitle = "Account summary";
  static override iconPath = "M3 4h18v3H3V4m0 5h18v11H3V9m3 4v3h6v-3H6";
  static override accountCard = true;
  protected override content() {
    const hass = this.hass as Hass;
    const choices = globalEntities(hass, "dashboard_balance");
    const balance = this.config.entity
      ? hass.states[this.config.entity]
      : choices.length === 1
        ? choices[0]
        : undefined;
    if (balance?.attributes.globird_sensor_key !== "dashboard_balance")
      return html`<p class="empty">Select the GloBird dashboard balance entity in the card editor.</p>`;
    const invoice = balance.attributes.latest_invoice;
    const info =
      invoice && typeof invoice === "object"
        ? (invoice as Record<string, unknown>)
        : {};
    const refreshes = globalEntities(hass, "refresh_status");
    return html`<div class="metrics">${this.metric("Account balance", balance, { unit: "AUD", note: "Negative = credit · positive = amount owing" })}${this.metric("Latest invoice", undefined, { n: number(info.amount), unit: "AUD", note: `Issued ${dateLabel(info.issuedDate, hass)}` })}</div><p class="subtitle">Invoice due: ${dateLabel(info.dueDate, hass)}</p>${refreshes.length === 1 ? html`<p class="notice" role="status">${refreshes[0]?.state === "ok" ? "Data refresh successful" : "Refresh failed or unavailable. Showing last successful data."} Last successful refresh: ${timestampLabel(refreshes[0]?.attributes.last_successful_refresh, hass)}.</p>` : html`<p class="subtitle">Refresh status is available in the integration diagnostics.</p>`}`;
  }
}
