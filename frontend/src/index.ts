import { AccountCard } from "./cards/account";
import { ElectricityUsageCard } from "./cards/electricity-usage";
import { LatestDayCard } from "./cards/latest-day";
import { UsageCostCard } from "./cards/usage-cost";
import { CardEditor } from "./editors/card-editor";
import type { Hass } from "./types";

// The GloBird sensors each card is suggested for in the card picker.
const suggestedFor: Record<string, readonly string[]> = {
  "globird-usage-cost-card": [
    "billing_period_cost",
    "expected_month_cost",
    "cost_total",
  ],
  "globird-electricity-usage-card": [
    "usage_total",
    "solar_export_total",
    "controlled_load_total",
  ],
  "globird-latest-day-card": [
    "latest_day_usage",
    "latest_day_cost",
    "latest_day_solar_export",
    "latest_gas_reading",
  ],
  "globird-account-card": ["dashboard_balance"],
};

declare global {
  interface Window {
    customCards?: {
      type: string;
      name: string;
      description: string;
      preview: boolean;
      documentationURL: string;
      getEntitySuggestion?: (
        hass: Hass,
        entityId: string,
      ) => { config: Record<string, unknown> } | null;
    }[];
  }
}
export function registerCards() {
  if (!customElements.get("globird-card-editor"))
    customElements.define("globird-card-editor", CardEditor);
  for (const [tag, card, description] of [
    [
      "globird-usage-cost-card",
      UsageCostCard,
      "Billing-period cost and a clearly labelled 30-day estimate.",
    ],
    [
      "globird-electricity-usage-card",
      ElectricityUsageCard,
      "General import, solar export and daily readings.",
    ],
    [
      "globird-latest-day-card",
      LatestDayCard,
      "Latest available usage and cost, or an actual gas meter reading.",
    ],
    [
      "globird-account-card",
      AccountCard,
      "Account balance, latest invoice and refresh status.",
    ],
  ] as const) {
    if (!customElements.get(tag)) customElements.define(tag, card);
    window.customCards ??= [];
    if (!window.customCards.some((c) => c.type === tag))
      window.customCards.push({
        type: tag,
        name: `GloBird ${card.cardTitle}`,
        description,
        preview: true,
        documentationURL:
          "https://github.com/tinkerologie/ha-globird#dashboard-cards",
        getEntitySuggestion: (hass: Hass, entityId: string) => {
          const key = hass.states[entityId]?.attributes.globird_sensor_key;
          return typeof key === "string" && suggestedFor[tag]?.includes(key)
            ? { config: { type: `custom:${tag}`, entity: entityId } }
            : null;
        },
      });
  }
}
registerCards();
