import { css } from "lit";
// Built on the Home Assistant design tokens (--ha-space-*, --ha-font-*,
// --ha-border-radius-*, semantic --ha-color-*), each with a fallback to the
// older theme variables so the cards also follow user themes and older frontends.
export const styles = css`
  :host {
    display: block;
    min-width: 0;
    color: var(--primary-text-color);
    font-family: var(--ha-font-family-body, Roboto, sans-serif);
  }
  * { box-sizing: border-box; }
  ha-card {
    display: block;
    height: 100%;
    overflow: hidden;
    background: var(--ha-card-background, var(--card-background-color));
    border-radius: var(--ha-card-border-radius, var(--ha-border-radius-lg, 12px));
    border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color));
    box-shadow: var(--ha-card-box-shadow, none);
  }
  header {
    padding: var(--ha-space-4, 16px) var(--ha-space-4, 16px) 0;
    display: flex;
    align-items: center;
    gap: var(--ha-space-3, 12px);
  }
  h2 {
    font-size: var(--ha-font-size-l, 16px);
    font-weight: var(--ha-font-weight-medium, 500);
    line-height: var(--ha-line-height-condensed, 1.2);
    margin: 0;
    overflow-wrap: anywhere;
  }
  .icon {
    color: var(--globird-accent-color, var(--primary-color));
    background: var(--ha-color-fill-primary-quiet-resting, var(--secondary-background-color));
    width: 36px;
    height: 36px;
    display: grid;
    place-items: center;
    border-radius: var(--ha-border-radius-circle, 50%);
    flex: none;
  }
  .icon svg { width: 20px; height: 20px; }
  .subtitle, p, small { color: var(--secondary-text-color); }
  .subtitle {
    font-size: var(--ha-font-size-m, 14px);
    line-height: var(--ha-line-height-normal, 1.6);
    margin: var(--ha-space-1, 4px) 0 0;
  }
  header .subtitle { font-size: var(--ha-font-size-s, 12px); margin: 2px 0 0; line-height: var(--ha-line-height-condensed, 1.2); }
  .body { padding: var(--ha-space-4, 16px); container-type: inline-size; }
  .metrics {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: var(--ha-space-2, 8px);
  }
  .metric {
    display: flex;
    flex-direction: column;
    gap: var(--ha-space-1, 4px);
    min-width: 0;
    min-height: 88px;
    align-items: flex-start;
    text-align: start;
    padding: var(--ha-space-3, 12px);
    border: 1px solid var(--ha-color-border-neutral-quiet, var(--divider-color));
    border-radius: var(--ha-border-radius-lg, 12px);
    background: transparent;
    color: inherit;
    font: inherit;
    cursor: pointer;
    transition: background-color var(--ha-animation-duration-fast, 150ms) ease-in-out;
  }
  .metric:not(:disabled):hover { background: var(--ha-color-fill-neutral-quiet-hover, var(--secondary-background-color)); }
  .metric:disabled { cursor: default; }
  .metric .label {
    font-size: var(--ha-font-size-s, 12px);
    line-height: var(--ha-line-height-condensed, 1.2);
    color: var(--secondary-text-color);
  }
  .value {
    font-size: clamp(var(--ha-font-size-xl, 20px), 8cqw, var(--ha-font-size-3xl, 28px));
    font-weight: var(--ha-font-weight-medium, 500);
    line-height: var(--ha-line-height-condensed, 1.2);
    font-variant-numeric: tabular-nums;
    overflow-wrap: anywhere;
  }
  .value.muted { color: var(--disabled-text-color, var(--secondary-text-color)); font-size: var(--ha-font-size-l, 16px); }
  .unit { font-size: var(--ha-font-size-m, 14px); font-weight: var(--ha-font-weight-normal, 400); white-space: nowrap; }
  .metric small { font-size: var(--ha-font-size-s, 12px); line-height: var(--ha-line-height-condensed, 1.2); }
  .alert {
    --alert-color: var(--ha-color-fill-primary-loud-resting, var(--info-color, var(--primary-color)));
    display: flex;
    align-items: flex-start;
    gap: var(--ha-space-2, 8px);
    margin: var(--ha-space-3, 12px) 0 0;
    padding: var(--ha-space-2, 8px) var(--ha-space-3, 12px);
    border-radius: var(--ha-border-radius-md, 8px);
    background: color-mix(in srgb, var(--alert-color) 12%, transparent);
    color: var(--primary-text-color);
    font-size: var(--ha-font-size-m, 14px);
    line-height: var(--ha-line-height-normal, 1.6);
    overflow-wrap: anywhere;
  }
  .alert svg { flex: none; width: 20px; height: 20px; margin-block-start: 2px; color: var(--alert-color); }
  .alert.warning { --alert-color: var(--ha-color-fill-warning-loud-resting, var(--warning-color, #ffa600)); }
  .alert.success { --alert-color: var(--ha-color-fill-success-loud-resting, var(--success-color, #43a047)); }
  fieldset {
    border: 0;
    display: flex;
    gap: var(--ha-space-1, 4px);
    padding: var(--ha-space-1, 4px);
    margin: 0 0 var(--ha-space-4, 16px);
    border-radius: var(--ha-border-radius-pill, 9999px);
    background: var(--ha-color-fill-neutral-quiet-resting, var(--secondary-background-color));
  }
  legend, .choice input {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
    white-space: nowrap;
  }
  .service-picker { display: flex; flex-direction: column; gap: var(--ha-space-2, 8px); margin-block: var(--ha-space-3, 12px); font-size: var(--ha-font-size-m, 14px); }
  .service-picker select {
    min-height: 44px;
    font: inherit;
    color: inherit;
    background: var(--ha-color-form-background, var(--card-background-color));
    border: 1px solid var(--ha-color-border-neutral-quiet, var(--divider-color));
    border-radius: var(--ha-border-radius-md, 8px);
    padding: var(--ha-space-2, 8px);
  }
  .choice {
    position: relative;
    flex: 1;
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 40px;
    border-radius: var(--ha-border-radius-pill, 9999px);
    cursor: pointer;
    font-size: var(--ha-font-size-m, 14px);
    font-weight: var(--ha-font-weight-medium, 500);
    color: var(--secondary-text-color);
  }
  .choice:has(input:checked) {
    background: var(--card-background-color);
    color: var(--primary-color);
    box-shadow: var(--ha-box-shadow-s, 0 1px 2px rgb(0 0 0 / 15%));
  }
  .choice:has(input:disabled) { cursor: default; opacity: 0.5; }
  :focus-visible, .choice:has(input:focus-visible) {
    outline: 2px solid var(--ha-color-focus, var(--primary-color));
    outline-offset: 2px;
  }
  details { margin-block-start: var(--ha-space-4, 16px); border-block-start: 1px solid var(--divider-color); }
  summary {
    min-height: 48px;
    display: flex;
    align-items: center;
    gap: var(--ha-space-2, 8px);
    cursor: pointer;
    list-style: none;
    font-size: var(--ha-font-size-m, 14px);
    font-weight: var(--ha-font-weight-medium, 500);
    color: var(--primary-text-color);
  }
  summary::-webkit-details-marker { display: none; }
  summary svg { margin-inline-start: auto; width: 24px; height: 24px; color: var(--secondary-text-color); transition: transform var(--ha-animation-duration-fast, 150ms) ease-in-out; }
  details[open] summary svg { transform: rotate(180deg); }
  details p { font-size: var(--ha-font-size-m, 14px); line-height: var(--ha-line-height-normal, 1.6); margin: 0 0 var(--ha-space-3, 12px); }
  .chart-mode { margin: var(--ha-space-4, 16px) 0 0; }
  .chart {
    --chart-import: var(--energy-grid-consumption-color, #488fc2);
    --chart-export: var(--energy-grid-return-color, #8353d1);
    --chart-controlled: var(--energy-non-fossil-color, #0f9d58);
    --chart-cost: var(--energy-grid-consumption-color, #488fc2);
    --chart-credit: var(--ha-color-fill-success-loud-resting, var(--success-color, #43a047));
    --chart-gas: var(--energy-gas-color, #8e021b);
    width: 100%;
    height: auto;
    display: block;
    margin-block-start: var(--ha-space-3, 12px);
    overflow: visible;
  }
  .chart text { fill: var(--secondary-text-color); font-size: 9px; font-variant-numeric: tabular-nums; }
  .chart .grid { stroke: var(--divider-color); stroke-width: 0.5; stroke-dasharray: 2 2; }
  .chart .zero { stroke: var(--secondary-text-color); stroke-width: 0.75; }
  .chart .import { fill: var(--chart-import); }
  .chart .export { fill: var(--chart-export); }
  .chart .controlled { fill: var(--chart-controlled); }
  .chart .cost { fill: var(--chart-cost); }
  .chart .credit { fill: var(--chart-credit); }
  .chart g:hover rect { opacity: 0.8; }
  .chart .gas-line { fill: none; stroke: var(--chart-gas); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
  .chart .gas-point { fill: var(--card-background-color); stroke: var(--chart-gas); stroke-width: 2; }
  .legend {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--ha-space-1, 4px) var(--ha-space-4, 16px);
    font-size: var(--ha-font-size-s, 12px);
    color: var(--secondary-text-color);
    margin-block-start: var(--ha-space-2, 8px);
  }
  .legend span::before {
    content: "";
    display: inline-block;
    width: 10px;
    height: 10px;
    margin-inline-end: 6px;
    vertical-align: -1px;
    border-radius: var(--ha-border-radius-sm, 4px);
    background: var(--legend-color);
  }
  .legend .import { --legend-color: var(--energy-grid-consumption-color, #488fc2); }
  .legend .export { --legend-color: var(--energy-grid-return-color, #8353d1); }
  .legend .controlled { --legend-color: var(--energy-non-fossil-color, #0f9d58); }
  .legend .cost { --legend-color: var(--energy-grid-consumption-color, #488fc2); }
  .legend .credit { --legend-color: var(--ha-color-fill-success-loud-resting, var(--success-color, #43a047)); }
  .legend .gas { --legend-color: var(--energy-gas-color, #8e021b); }
  .legend .gas::before { border-radius: var(--ha-border-radius-circle, 50%); }
  .legend .unit-label { margin-inline-start: auto; }
  .legend .unit-label::before { display: none; }
  table { width: 100%; border-collapse: collapse; font-size: var(--ha-font-size-s, 12px); font-variant-numeric: tabular-nums; }
  th, td { padding: var(--ha-space-2, 8px) 3px; text-align: end; border-block-end: 1px solid var(--divider-color); }
  th:first-child, td:first-child { text-align: start; }
  caption { text-align: start; padding: var(--ha-space-2, 8px) 0; color: var(--secondary-text-color); }
  .empty { line-height: var(--ha-line-height-normal, 1.6); margin: 0; }
  .full { grid-column: 1 / -1; }
  @container (max-width: 270px) {
    .metrics { grid-template-columns: 1fr; }
    .value { font-size: var(--ha-font-size-2xl, 24px); }
  }
  @media (prefers-reduced-motion: reduce) {
    * { animation: none !important; transition: none !important; }
  }
`;
