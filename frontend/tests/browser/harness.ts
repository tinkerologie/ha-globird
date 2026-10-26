import { syntheticHass } from "../fixtures";

const params = new URLSearchParams(location.search);
const dark = params.get("dark") === "true";
document.documentElement.style.cssText = `--primary-text-color:${dark ? "#e6e6e6" : "#202124"};--secondary-text-color:${dark ? "#b5b5b5" : "#616161"};--card-background-color:${dark ? "#202124" : "#ffffff"};--secondary-background-color:${dark ? "#303134" : "#f1f3f4"};--primary-color:${dark ? "#90caf9" : "#1565c0"};--text-primary-color:${dark ? "#101010" : "#ffffff"};--divider-color:${dark ? "#555" : "#ddd"};background:${dark ? "#121212" : "#fafafa"};font-family:Roboto,Arial,sans-serif;color:var(--primary-text-color);`;
const style = document.createElement("style");
style.textContent =
  "body{margin:16px}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:16px;align-items:start}ha-card{display:block}globird-card-editor{display:block;max-width:500px}";
document.head.append(style);
const module = document.createElement("script");
module.type = "module";
module.src = "/cards.js";
document.head.append(module);
module.onload = async () => {
  const h = syntheticHass();
  const mode = params.get("mode");
  if (mode === "unavailable") {
    for (const e of Object.values(h.states))
      if (e.attributes.account_service_id === "electric-demo")
        e.state = "unavailable";
  }
  if (mode === "stale" && h.states["sensor.demo_refresh_status"])
    h.states["sensor.demo_refresh_status"].state = "error";
  const root = document.querySelector("main");
  for (const tag of [
    "globird-usage-cost-card",
    "globird-electricity-usage-card",
    "globird-latest-day-card",
    "globird-account-card",
  ]) {
    const c = document.createElement(tag) as HTMLElement & {
      setConfig: (c: unknown) => void;
      hass?: unknown;
    };
    c.setConfig({ type: `custom:${tag}` });
    if (mode !== "loading") c.hass = h;
    root?.append(c);
  }
  if (params.has("editor")) {
    const c = document.createElement("globird-card-editor") as HTMLElement & {
      setConfig: (c: unknown) => void;
      hass?: unknown;
    };
    c.setConfig({ type: `custom:${params.get("editor")}` });
    c.hass = h;
    root?.append(c);
  }
  // A distinct URL forces module evaluation twice, verifying custom-element guards.
  const duplicate = document.createElement("script");
  duplicate.type = "module";
  duplicate.src = "/cards.js?second";
  document.head.append(duplicate);
};
