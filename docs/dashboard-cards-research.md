# GloBird dashboard card research

Research date: 26 October 2026. Scope: [enhancement #27](https://github.com/tinkerologie/ha-globird/issues/27).

## Home Assistant design and API requirements

- Use `ha-card` as the themed container and bundle Lit. Home Assistant does not publish a stable component library for other internal `ha-*` controls; avoid depending on their implementation details. [Custom UI tooling](https://contributors.home-assistant.io/frontend/custom-ui/)
- Implement validated `setConfig`, efficient `hass` updates, `getCardSize` for masonry, and `getGridOptions` for Sections. The Sections grid has 12 columns; choose widths in multiples of three and allow content to wrap. Use HA entity formatters for displayed state and names. [Card contract](https://contributors.home-assistant.io/frontend/custom-ui/card/)
- Register discoverable metadata in `window.customCards`, provide `getStubConfig`, and offer a visual editor. Current documentation supports `getConfigForm` schemas rendered by Home Assistant, avoiding direct construction of internal form controls. `getConfigElement` remains available for a custom editor and takes precedence when both exist. [Editor contract](https://contributors.home-assistant.io/frontend/custom-ui/card-editor/)
- Documentation describes the current frontend, not every deployed version. Confirm the minimum supported frontend implements `getConfigForm` before relying on it alone. A custom `getConfigElement` editor using native labelled controls is the compatibility option; emit bubbling, composed `config-changed` events containing the full configuration.
- Use semantic theme variables with classic variable fallbacks for text, muted text, card background, and borders. Use logical CSS properties for RTL. Keep the GloBird identity restrained; preserve user-selected themes. [Theming](https://contributors.home-assistant.io/frontend/architecture/theming/)
- Use HA font and spacing tokens. Preserve the hierarchy of the supplied screenshots without copying their oversized uppercase headings or fixed black surfaces. [Typography](https://contributors.home-assistant.io/design/foundations/typography/), [Foundations](https://contributors.home-assistant.io/design/foundations/)
- Provide keyboard access, visible focus, accessible names, and semantic headings. Aim for WCAG AA contrast; use text or icons alongside color. Prefer 44–48 pixel touch areas. Check narrow layouts, 200% zoom, light/dark themes, and assistive technology. [Accessibility](https://contributors.home-assistant.io/design/foundations/accessibility/)
- Respect reduced motion; avoid information conveyed only through animation. [Motion](https://contributors.home-assistant.io/design/foundations/motion/)
- Sensor interactions should open entity details. The frontend's `hass-more-info` event carries `{ entityId }`. Use current `perform-action` terminology if service actions become necessary. [Handler source](https://github.com/home-assistant/frontend/blob/dev/src/panels/lovelace/common/handle-action.ts), [Dashboard actions](https://www.home-assistant.io/dashboards/actions/)
- Serve one bundled JavaScript module and register the resource once, with a versioned URL for cache invalidation. Classic `js` resources are deprecated. Served assets must contain no account credentials. [Resource registration](https://contributors.home-assistant.io/frontend/custom-ui/resources/)

## TypeScript 7

Live registry checks returned `typescript` version `7.0.2` and its `tsc` executable. Use this stable compiler for type checking, with a separate bundler. The older `@typescript/native-preview` name is unnecessary. TypeScript 7.0 lacks the previous JavaScript compiler API, so tools importing that API need verified compatibility or the official TypeScript 6 compatibility alias. Avoid removed options such as `baseUrl`, ES5 targets, and old node/classic resolution. [Microsoft announcement](https://devblogs.microsoft.com/typescript/announcing-typescript-7-0/)

## Additional GloBird screens

The [official app page](https://www.globirdenergy.com.au/app/) links these first-party screenshots:

| Image | Published feature/caption |
| --- | --- |
| [EnergyMonitor](https://www.globirdenergy.com.au/wp-content/themes/globird-energy/images/app-feature-EnergyMonitor.webp) | Energy usage and daily insight |
| [Dash](https://www.globirdenergy.com.au/wp-content/themes/globird-energy/images/app-feature-Dash.webp) | Bills, invoices, and payments |
| [ZEROHERO](https://www.globirdenergy.com.au/wp-content/themes/globird-energy/images/app-feature-ZEROHERO.webp) | Battery management and status |
| [Account](https://www.globirdenergy.com.au/wp-content/themes/globird-energy/images/app-feature-Account.webp) | Account details and services |
| [SelfRead](https://www.globirdenergy.com.au/wp-content/themes/globird-energy/images/app-feature-SelfRead.webp) | Meter self-read upload |
| [Refer](https://www.globirdenergy.com.au/wp-content/themes/globird-energy/images/app-feature-Refer.webp) | Referral invitation |

The [Australian App Store listing](https://apps.apple.com/au/app/globird/id6479334165) supplies additional screenshot references and release notes covering budget tracking and predicted bills, ZEROHERO benefits and pending meter data, plan rates and time-of-use periods, and WHOLESAVE price/battery charts.

Evidence limitation: screenshot URLs and published captions/release notes were verified; not every remote image was visually inspected. EnergyMonitor and Account image requests failed in the research fetch. Feature availability and marketing screenshots do not prove that the integration's existing authenticated API exposes those features.

## Scaffolding references and data boundaries

The user's existing local integrations provide useful patterns, rather than an instruction to copy unrelated functionality:

- `../unraid-management-agent/ha-unraid-management-agent/frontend/`: Lit card base, registration, configuration editor, TypeScript 7 build, and browser tests; `custom_components/unraid_management_agent/frontend.py` provides integration resource-serving precedent.
- `../ha-unraid/ha-unraid/frontend/`: reusable dashboard base, registration, themed styles, Sections sizing, visual editor, and frontend tests; `custom_components/unraid/frontend.py` provides resource lifecycle precedent.
- `../ha-unifi-insights/frontend/`: discoverable card metadata, focused cards, editor and shared styles, browser/accessibility checks, and compiler compatibility aliases; `custom_components/unifi_insights/frontend.py` provides resource registration precedent.

Use GloBird backend entities and attributes as the source of truth. Preserve existing cost calculations, including credits; do not recalculate bills in the browser. Label predictions and optional local budget comparisons explicitly. A missing reading is not zero, and a missing metric should have an understandable unavailable/pending state. Gas meter indexes are not daily consumption. Keep electricity, solar exports, and gas units distinct. Battery control, wholesale trading actions, payments, referrals, and self-read submission require separate supported APIs and are outside this card enhancement's scope.

## Implemented compatibility decision

The authorised container runs Home Assistant Core 2026.10.4 with frontend 20260930.5 (Container install). The [Core manifest](https://github.com/home-assistant/core/blob/2026.10.4/homeassistant/components/frontend/manifest.json) pins this frontend. Its [element editor](https://github.com/home-assistant/frontend/blob/20260930.5/src/panels/lovelace/editor/hui-element-editor.ts) checks `getConfigElement()` before `getConfigForm()`. The coding plan also verified that ordering in frontends 20250903.2 and 20260527.5, associated with Core 2025.9.0 and 2026.6.2. The first release containing frontend PR 16142 remains unverified. Use a bundled native-control `getConfigElement()` editor for the minimum supported Core 2025.9.0.

`StaticPathConfig`, `async_register_static_paths` and `add_extra_js_url` were verified in the deployed container. The APIs also exist in the [2025.9 HTTP source](https://github.com/home-assistant/core/blob/2025.9.0/homeassistant/components/http/__init__.py) and [2026.6 frontend source](https://github.com/home-assistant/core/blob/2026.6.2/homeassistant/components/frontend/__init__.py). Registration uses these supported helpers, without mutating Lovelace resource storage.

The CodeRabbit plan reported Exa and Tavily unavailable in its own research environment. Both were available and used in this implementation session; the first-party screenshot URLs and surrounding captions above were verified with both services. This distinction preserves the actual evidence rather than repeating the plan's environment limitation. The user's explicit request to use the existing GloBird dashboard authorises saved test cards on that dashboard, superseding the plan's unsaved-preview restriction.
