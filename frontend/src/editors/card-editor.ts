import { css, html, LitElement } from "lit";
import { globalEntities, services } from "../data";
import type { CardConfig, Entity, Hass, Service } from "../types";

// Friendly names follow the device and entity naming of Home Assistant 2026.11.
const entityName = (e: Entity) =>
  typeof e.attributes.friendly_name === "string"
    ? `${e.attributes.friendly_name} (${e.entity_id})`
    : e.entity_id;
const siteLabel = (s: Service) => {
  const any = Object.values(s.entities)[0];
  const site = any?.attributes.site_identifier;
  return typeof site === "string" && site
    ? `site ${site}`
    : (any?.entity_id ?? "");
};
export class CardEditor extends LitElement {
  static override properties = {
    hass: { attribute: false },
    config: { attribute: false },
  };
  declare hass?: Hass;
  declare config: CardConfig;
  static override styles =
    css`:host{display:block;color:var(--primary-text-color);font:inherit}label{display:flex;flex-direction:column;gap:8px;margin-block:16px}label.check{flex-direction:row;align-items:center;gap:12px;min-height:48px}label.check input{width:20px;min-height:20px;height:20px;accent-color:var(--primary-color)}input,select{font:inherit;color:inherit;background:var(--card-background-color);border:1px solid var(--divider-color);border-radius:8px;padding:12px;min-height:48px;width:100%;box-sizing:border-box}fieldset{border:1px solid var(--divider-color);border-radius:8px;padding:12px}legend{font-size:14px}p{font-size:13px;line-height:1.5;color:var(--secondary-text-color)}:focus-visible{outline:3px solid var(--primary-color);outline-offset:2px}`;
  constructor() {
    super();
    this.config = { type: "" };
  }
  setConfig(config: CardConfig) {
    this.config = { ...config };
  }
  private change(key: keyof CardConfig, event: Event) {
    const control = event.target as HTMLInputElement;
    const next = { ...this.config };
    if (key === "show_temperature") {
      if (control.checked) delete next.show_temperature;
      else next.show_temperature = false;
    } else if (control.value === "") delete next[key];
    else if (key === "history_days") {
      const n = Number(control.value);
      if (!Number.isInteger(n) || n < 1 || n > 31) {
        control.value = String(this.config.history_days ?? 7);
        return;
      }
      next.history_days = n;
    } else Object.assign(next, { [key]: control.value });
    this.config = next;
    this.dispatchEvent(
      new CustomEvent("config-changed", {
        detail: { config: { ...next } },
        bubbles: true,
        composed: true,
      }),
    );
  }
  protected override render() {
    const account = this.config.type === "custom:globird-account-card";
    const choices = this.hass
      ? account
        ? globalEntities(this.hass, "dashboard_balance").map((e, i) => ({
            id: e.entity_id,
            label: `Account ${i + 1} · ${entityName(e)}`,
          }))
        : services(this.hass).map((s) => ({
            id:
              Object.values(s.entities).find(
                (e) => e.attributes.globird_sensor_key === "latest_data_status",
              )?.entity_id ??
              Object.values(s.entities)[0]?.entity_id ??
              "",
            label: `${s.type === "gas" ? "Gas" : "Electricity"} · ${siteLabel(s)}`,
          }))
      : [];
    // Preserve any explicitly configured companion entity rather than replacing it on render.
    if (this.config.entity && !choices.some((c) => c.id === this.config.entity))
      choices.push({ id: this.config.entity, label: this.config.entity });
    return html`<label>${account ? "Account balance entity" : "GloBird service"}<select aria-label=${account ? "Account balance entity" : "GloBird service"} .value=${this.config.entity ?? ""} @change=${(e: Event) => this.change("entity", e)}><option value="">Choose explicitly (recommended)</option>${choices.map((c) => html`<option value=${c.id} .selected=${this.config.entity === c.id}>${c.label}</option>`)}</select></label><p>Select a service explicitly when several accounts or services are available. Entity names are shown only in this editor.</p><label>Title (optional)<input .value=${this.config.title ?? ""} @input=${(e: Event) => this.change("title", e)}></label>${account ? "" : html`<fieldset><legend>Service and daily history</legend><label>Default service type<select .value=${this.config.default_service_type ?? "electricity"} @change=${(e: Event) => this.change("default_service_type", e)}><option value="electricity">Electricity</option><option value="gas">Gas</option></select></label><label>History source<select .value=${this.config.history_source ?? "attributes"} @change=${(e: Event) => this.change("history_source", e)}><option value="attributes">Recent attributes (up to 7 days)</option><option value="statistics">Recorder statistics (up to 31 days)</option></select></label><label>History days<input type="number" min="1" max="31" step="1" .value=${String(this.config.history_days ?? 7)} @change=${(e: Event) => this.change("history_days", e)}></label><label class="check"><input type="checkbox" .checked=${this.config.show_temperature !== false} @change=${(e: Event) => this.change("show_temperature", e)}>Show daily temperatures in the chart</label><p>Statistics reads existing daily changes, including each register and charge category. No extra GloBird portal requests are made.</p></fieldset>`}`;
  }
}
