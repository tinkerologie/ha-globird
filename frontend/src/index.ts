import { AccountCard } from "./cards/account";
import { ElectricityUsageCard } from "./cards/electricity-usage";
import { LatestDayCard } from "./cards/latest-day";
import { UsageCostCard } from "./cards/usage-cost";
import { CardEditor } from "./editors/card-editor";

declare global {
  interface Window {
    customCards?: {
      type: string;
      name: string;
      description: string;
      preview: boolean;
      documentationURL: string;
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
      });
  }
}
registerCards();
