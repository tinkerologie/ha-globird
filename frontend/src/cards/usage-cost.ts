import { html } from "lit";
import { dateLabel, number } from "../data";
import type { Hass } from "../types";
import { chevron, GloBirdCard } from "./base";
export class UsageCostCard extends GloBirdCard {
  static override cardTitle = "Usage and cost";
  static override iconPath =
    "M3 3h2v16h16v2H3V3m5 7h3v6H8v-6m5-5h3v11h-3V5m5 3h3v8h-3V8";
  protected override content() {
    const e = this.service?.entities ?? {},
      h = this.hass as Hass;
    const projection = e.expected_month_cost;
    const pending = e.latest_data_status?.state === "no_data";
    const completed = number(projection?.attributes.completed_days);
    return html`<div class="metrics">${this.metric("Cost so far", pending ? undefined : e.billing_period_cost, { unit: "AUD", note: "Billing period" })}${this.metric("Completed days", projection, { n: completed, unit: "days" })}${this.metric("Estimated bill", projection, { unit: "AUD", note: "30-day estimate" })}${this.metric("Latest complete day cost", e.latest_day_cost, { unit: "AUD", note: dateLabel(e.latest_day_cost?.attributes.latest_day, h) })}</div><p class="subtitle">Period start: ${dateLabel(projection?.attributes.billing_period_start ?? e.billing_period_cost?.attributes.billing_period_start, h)} · from invoice issue date</p><details><summary>How this estimate is calculated${chevron}</summary><p>Estimated bill = billing-period cost to date ÷ completed days with cost data × 30 days. This is an estimate, not a bill. GloBird costs include the charges and credits supplied by the portal.</p><p>Cost data through ${dateLabel(projection?.attributes.latest_day, h)}. Meter and cost data can arrive 24–48 hours later.</p></details>`;
  }
}
