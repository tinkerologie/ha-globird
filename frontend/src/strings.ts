const en = {
  loading: "Waiting for GloBird entities…",
  choose: "Select a GloBird service in the card editor.",
  unavailable: "Unavailable",
  noData: "No data",
  yesterday: "Yesterday",
  latest: "Latest available",
  electricity: "Electricity",
  gas: "Gas",
  waiting_for_cost: "Usage is available. Waiting for complete cost data.",
  waiting_for_usage: "Cost data is available. Waiting for meter readings.",
  no_data: "Data pending. GloBird has not supplied readings yet.",
  stale: "Refresh failed. Showing the last successful data.",
  incomplete: "Some cost days are incomplete and excluded from comparisons.",
  historyError:
    "Statistics could not be loaded. Showing recent attribute history.",
};
export type StringKey = keyof typeof en;
const languages: Record<string, Partial<typeof en>> = { en };
export function text(key: StringKey, language = "en"): string {
  return languages[language.split("-")[0] ?? "en"]?.[key] ?? en[key];
}
