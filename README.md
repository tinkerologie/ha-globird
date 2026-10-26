# GloBird Integration for Home Assistant

<!-- BADGES:START -->
[![Marketplace and HACS](https://img.shields.io/badge/Marketplace%20%7C%20HACS-Default-orange.svg)](https://www.hacs.xyz/docs/marketplace/)
[![GitHub Last Commit](https://img.shields.io/github/last-commit/tinkerologie/ha-globird)](https://github.com/tinkerologie/ha-globird/commits/main)
[![GitHub Release](https://img.shields.io/github/v/release/tinkerologie/ha-globird)](https://github.com/tinkerologie/ha-globird/releases)
[![codecov](https://codecov.io/gh/tinkerologie/ha-globird/graph/badge.svg)](https://codecov.io/gh/tinkerologie/ha-globird)
[![License](https://img.shields.io/github/license/tinkerologie/ha-globird)](./LICENSE)
<!-- BADGES:END -->

The **GloBird** custom integration connects your [GloBird Energy](https://www.globirdenergy.com.au/) Australian electricity and gas customer portal account to Home Assistant. It retrieves account balances, invoices, smart/basic meter electricity usage (`E1` grid import and `B1` solar feed-in export), gas meter readings, daily costs, solar export credits, ZeroHero status, and local weather observations, and integrates directly with the **Home Assistant Energy Dashboard**.

---

## Supported Services & Devices

- **Electricity Services (`Power`)**:
  - Smart / Interval meters (`E1` general/time-of-use import and `B1` solar export registers)
  - Basic electricity meters
  - GloBird plans including **ZEROHERO** (tracks daily credit achievement and cutoff boundaries)
- **Gas Services (`Gas`)**:
  - Basic index meters (cubic metres `m³` with serial-aware meter replacement handling) and daily gas cost summaries
- **Newly Transferred / In-Progress Accounts**:
  - Accounts in `Switched` or `PendingSwitchResults` states (where smart or gas meter reads have not yet been published by the distributor) are supported cleanly. Account, service status, signup progress, and weather entities populate immediately while usage and cost entities remain safely idle until the first meter reads arrive.

---

## Installation

### Option 1: HACS (Recommended)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=tinkerologie&repository=ha-globird&category=integration)

1. Open **HACS** in Home Assistant.
2. Add `https://github.com/tinkerologie/ha-globird` as a custom **Integration** repository.
3. Install **GloBird** and restart Home Assistant.
4. Go to **Settings > Devices & Services > Add Integration** and search for **GloBird**.

### Option 2: Manual Installation

1. Copy the `custom_components/globird` directory into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.
3. Go to **Settings > Devices & Services > Add Integration** and select **GloBird**.

---

## Configuration Parameters

### Initial Setup (`Settings > Devices & Services > Add Integration`)

| Parameter | Description |
| --- | --- |
| **Email** | The email address used to sign in to `myaccount.globirdenergy.com.au`. |
| **Password** | Your GloBird customer portal password (encrypted using RSA-OAEP SHA-256 against GloBird's public JWK prior to authentication). |

### Integration Options (`Configure` button on the GloBird entry)

| Option | Default | Description |
| --- | --- |
| **Daily polling start time** | `00:05` | Local time of day when automatic polling resumes after the previous day's electricity usage and cost data have both been marked `ready`. |

### Re-authentication & Reconfiguration

- If your GloBird password changes, Home Assistant will automatically prompt you to re-authenticate, or you can select **Reconfigure** from the integration's three-dot menu in **Settings > Devices & Services**.

---

## Data Update Schedule

- **Readiness Polling**: Polls every **30 minutes** until the previous calendar day's electricity usage and complete cost rows (more than the early fixed supply charge) have been published by the portal.
- **Idle Window**: Once yesterday's electricity usage and cost data are both `ready`, polling pauses until the configured **Daily polling start time** (default `00:05` the next day) to minimize unnecessary portal requests.
- **Session Persistence**: Session cookies (`ARRAffinity` sticky-routing and portal auth cookies) and last-known payloads are cached in Home Assistant storage so restarts do not trigger redundant logins.

---

## Home Assistant Energy Dashboard Setup

Go to **Settings > Dashboards > Energy** to configure usage and cost tracking:

### 1. Electricity Grid Consumption & Costs
- **Consumed Energy (`Grid consumption`)**:
  - Select `sensor.glo_bird_energy_recent_usage_total` (*Recent Usage Total*) or `sensor.glo_bird_energy_latest_day_usage` (*Latest Day Usage*), **or** the backfilled external statistic `globird:<entry>_service_<id>_usage_total`.
  - **Controlled load**: if your account has a controlled-load register, also add `globird:<entry>_service_<id>_controlled_load_total` (*Recent Controlled Load Total*) as a second grid consumption source. It is not part of *Recent Usage Total*.
  - **Time-of-use windows** (optional): instead of the usage total, you can add one grid consumption source per register statistic, `globird:<entry>_service_<id>_register_<register>` (for example `..._register_e1_peak_usage`), each with its own price. Use either the total or the registers, never both, or usage is counted twice.
- **Cost Tracking (`Use an entity tracking the total costs`)**:
  - Select `sensor.glo_bird_energy_billing_period_cost` (*Billing Period Cost*), `sensor.glo_bird_energy_recent_cost_total` (*Recent Cost Total*), or `sensor.glo_bird_energy_latest_daily_cost` (*Latest Daily Cost*).

### 2. Solar Export (`Return to grid`) & Feed-in Compensation
- **Returned Energy (`Return to grid`)**:
  - Select `sensor.glo_bird_energy_recent_solar_export_total` (*Recent Solar Export Total*) or `sensor.glo_bird_energy_latest_day_solar_export` (*Latest Day Solar Export*). Plans with several feed-in windows also get one `globird:<entry>_service_<id>_register_<register>` statistic per window; as above, use either the total or the windows.
- **Compensation (`Use an entity tracking total compensation`)**:
  - Select `sensor.glo_bird_energy_recent_solar_export_credit_total` (*Recent Solar Export Credit Total*) or `sensor.glo_bird_energy_latest_daily_solar_export_credit` (*Latest Daily Solar Export Credit*).

### How usage registers are counted

The portal returns one row per meter register and day (`E1` import, `B1` export, and so on). Only rows whose `chargeCategoryCode` is an energy category count towards the usage, export and controlled-load totals: `USAGE`, `CONTROL`, `CLIMATE` and `SOLAR` (the same list GloBird's own portal totals), plus rows without a category. Other rows, such as ZEROHERO's `ZeroHero` (`LOW_USAGE_REWARD_PER_DAY`, 18:00–21:00) and `Super Export top up` (`ADDON_FEED_IN`, 18:00–21:00), only re-report part of a time-of-use window for a reward, so they are listed in the `registers` attribute with `usage_class: tracking` but not added to any total. Rows with category `CONTROL` are controlled load; every other import row is general import.

The daily `globird:` statistics are imported again on every refresh for the last 31 days the portal returns. Each import continues the running total from the last stored row before that window, so older days stay in your long-term statistics after the portal stops returning them.

### 3. Gas Consumption & Costs
- **Gas Usage**:
  - Select the external statistic `globird:<entry>_service_<id>_latest_gas_reading` (`m³`), named *Latest Gas Reading (<mirn>)*. The integration imports every published meter read into it, and its sum starts at 0 at the first read, so only gas used between reads counts.
  - Do not select the `sensor.glo_bird_energy_latest_gas_reading_<mirn>` entity. It shows the current meter index, has no state class, and does not record long-term statistics: basic gas meters are read about every three months, so the entity cannot produce correct hourly usage. It is `unknown` until the first read is published.
- **Gas Cost**:
  - Select `sensor.glo_bird_energy_billing_period_cost_<mirn>` (*Billing Period Cost*) or `sensor.glo_bird_energy_recent_cost_total_<mirn>` (*Recent Cost Total*).

---

## Provided Entities

### Account-Level Sensors
- **Balance** (`AUD`, `monetary`, `total`) — Current account balance (negative = credit, positive = amount owing).
- **Dashboard Balance** (`AUD`, `monetary`, `total`) — Portal dashboard balance with recent transactions and correspondence attributes.
- **Latest Invoice** (`AUD`, `monetary`) — Most recent invoice amount and metadata.
- **Signup Services** (`diagnostic`) — Number of services in transfer/signup state and transfer progress details.
- **Last Successful Refresh** (`timestamp`, `diagnostic`) — UTC timestamp of the last portal refresh.
- **Refresh Status** (`diagnostic`) — `ok` or `error`, with per-endpoint error details.

### Service-Level Sensors (Electricity & Gas)
- **Service Status** (`diagnostic`) — Portal status (e.g. `Switched`, `PendingSwitchResults`, `Active`).
- **Meter Info** (`diagnostic`) — Selected meter read type (`SMART` / `BASIC`) and serial metadata.
- **Latest Data Date** & **Latest Data Status** (`diagnostic`) — Readiness state (`ready`, `waiting_for_cost`, `waiting_for_usage`, `no_data`).
- **Recent Usage Total** & **Latest Day Usage** (`kWh`, `energy`, `total`) — General grid import usage (`E1`), without reward/add-on tracking rows and without controlled load.
- **Recent Solar Export Total** & **Latest Day Solar Export** (`kWh`, `energy`, `total`) — Solar feed-in export (`B1`), without add-on tracking rows such as *Super Export top up*.
- **Recent Controlled Load Total** & **Latest Day Controlled Load** (`kWh`, `energy`, `total`) — Created only for services whose portal data has a controlled-load (`CONTROL`) register.
- **Recent `<register>`** (`kWh`, `energy`, `total`), for example *Recent E1 Peak Usage* or *Recent B1 Solar/Generation Feed in (4pm-11pm)* — One sensor per register when a service has more than one register of the same kind (time-of-use import windows, feed-in windows, several controlled loads). Flat-rate accounts get none. Attributes include the register's `time_periods` (for example `12:00`–`15:00` for a free or off-peak window), `latest_day`, `latest_day_usage` and the last seven days. The sensor is created when the portal first returns the register and is unavailable while the portal stops returning it; delete it yourself if your plan no longer has that register.
- **Recent Cost Total**, **Latest Daily Cost**, & **Billing Period Cost** (`AUD`, `monetary`, `total`) — Net service cost totals.
- **Recent Solar Export Credit Total** & **Latest Daily Solar Export Credit** (`AUD`, `monetary`, `total`) — Solar feed-in credit totals.
- **Expected Monthly Cost** (`AUD`, `monetary`) & **Billing Period Days** — Billing cycle cost projection.
- **ZeroHero Status** (`enum`: `achieved`, `missed`, `pending`, `awaiting_result`, `unknown`) — Daily ZeroHero credit status.
- **Latest Gas Reading** (`m³`, `gas`, no state class; `unknown` until the first read) & **Latest Gas Reading Date** (`diagnostic`). Gas usage for the Energy dashboard comes from the `globird:` external statistic (see *Gas Consumption & Costs*).
- **Weather Summary** (`°C`, `temperature`, `measurement`) — Daily min/max temperatures for the service postcode.

---

## Example Automations

### Notify When Yesterday's Usage & Cost Data Are Ready

```yaml
automation:
  - alias: "GloBird Daily Summary Notification"
    trigger:
      - platform: state
        entity_id: sensor.glo_bird_energy_latest_data_status
        to: "ready"
    action:
      - action: notify.persistent_notification
        data:
          title: "GloBird Energy Update ({{ states('sensor.glo_bird_energy_latest_data_date') }})"
          message: >
            Usage: {{ states('sensor.glo_bird_energy_latest_day_usage') }} kWh
            Solar Export: {{ states('sensor.glo_bird_energy_latest_day_solar_export') }} kWh
            Net Cost: ${{ states('sensor.glo_bird_energy_latest_daily_cost') }} AUD
            ZeroHero: {{ states('sensor.glo_bird_energy_zerohero_status') }}
```

---

## Known Limitations & Troubleshooting

- **Distributor Meter Data Delay**: Australian smart meter data is typically published 24–48 hours in arrears, and basic gas meter reads are published following scheduled distributor reads.
- **Accounts in Setup / Transfer (`Switched` / `PendingSwitchResults`)**: When a new GloBird account is still transferring and no meter has been assigned by the distributor yet, `readmeters` and `CostDetail` return empty lists (`[]`). Usage and cost sensors will display `Unknown` (`None`) and `Latest Data Status` will report `no_data` until the first meter read is published.
- **Captcha Enforcement**: If the GloBird portal triggers hCaptcha/reCaptcha due to repeated failed logins, wait a few minutes and sign in once via a web browser before retrying **Reconfigure**.
- **Diagnostics**: You can download a redacted diagnostics JSON bundle from **Settings > Devices & Services > GloBird > Download Diagnostics** when reporting an issue.

---

## Removing the Integration

1. Go to **Settings > Devices & Services** and select **GloBird**.
2. Click the three-dot menu next to your GloBird config entry and choose **Delete**.
3. If installed via HACS, open **HACS > GloBird > Remove** and restart Home Assistant.


## Dashboard cards

Four cards ship with the integration. Restart Home Assistant after updating, then refresh the browser. In storage mode, the integration manages one versioned Lovelace module resource automatically; no HACS frontend download or manual resource is needed. Loading through Lovelace ensures Home Assistant has installed its custom-element registry before the cards register. Open **Edit dashboard → Add card** and search for **GloBird**. Each card has a visual editor with a service/entity selector, optional title, default service type, history source and history length.

| Type | Contents |
| --- | --- |
| `custom:globird-usage-cost-card` | Billing-period cost and days, estimated bill, latest complete cost day |
| `custom:globird-electricity-usage-card` | Separate general import, solar export and controlled load, daily averages and chart |
| `custom:globird-latest-day-card` | Latest available usage and matching cost, or an actual gas meter reading |
| `custom:globird-account-card` | Account balance, invoice and refresh status |

Choose an existing GloBird service sensor in the editor. The companion sensors are discovered through `globird_sensor_key`, so their names can be customised. Select an account explicitly when more than one is present. Electricity/gas selection appears only when that account has both services. Account cards use the **Dashboard Balance** entity; they do not show account numbers or addresses.

```yaml
type: custom:globird-electricity-usage-card
entity: sensor.globird_energy_latest_data_status
history_source: attributes
history_days: 7
```

```yaml
type: custom:globird-usage-cost-card
entity: sensor.globird_energy_latest_data_status
title: Energy costs
```

```yaml
type: custom:globird-latest-day-card
entity: sensor.globird_energy_latest_data_status
```

```yaml
type: custom:globird-account-card
entity: sensor.globird_energy_dashboard_balance
```

Use your actual entity IDs. For longer electricity history, choose `history_source: statistics` and `history_days: 31` (1–31 is supported). This reads `recorder/statistics_during_period` daily **change** values using the existing `statistic_id`, not cumulative sums. Attribute history is limited to the latest seven rows. The chart and its accessible readings table show dates and missing values explicitly. Per-day averages use only days with readings; cost comparisons use matching complete usage/cost days. Controlled load is never added into general import by the cards.

GloBird readings and costs may lag by 24–48 hours. **Yesterday** appears only when the reading date matches yesterday in Home Assistant's configured time zone. Gas values are meter indexes in m³, not daily consumption; missing readings remain **No data**. Zero is retained as a real value. Account balances retain the existing convention: negative means credit, positive means money owing.

The estimated bill is the integration's existing **30-day projection**, calculated as billing-period cost to date ÷ completed days with cost data × 30. The start is inferred from the latest invoice issue date and is labelled accordingly. It is not the retailer's final bill. The cards preserve portal costs and credits; they do not calculate tariff prices, budgets or battery forecasts. Failed refreshes show stale-data notices and the last successful refresh date.

Both discovery attributes are excluded from recorder attributes. No credentials or portal API calls are included in the frontend bundle. The module remains registered when a config entry reloads or unloads. If HTTP/frontend is absent, sensors continue working without the cards.

For development, use Node 24 (`frontend/.nvmrc`), run `npm ci` in `frontend`, and run `script/frontend`. TypeScript is pinned to stable **7.0.2** with `tsc --noEmit`; Lit is bundled locally. `npm run verify-bundle` rebuilds and rejects a bundle that differs from the committed asset. Research and compatibility evidence are in [dashboard-cards-research.md](docs/dashboard-cards-research.md).

### YAML-mode dashboard resources

For YAML-mode Lovelace, declare the module in your existing resources configuration so it loads after the Home Assistant frontend starts. The optional extra-module fallback is retained, but an explicit YAML resource avoids early registration before Home Assistant installs its scoped registry. Keep the query version aligned with your installed integration version and change it when updating.

```yaml
resources:
  - url: /globird_frontend/globird-cards.js?v=2026.10.4
    type: module
```

The CI coverage report compares Python coverage with the actual PR base and requires no regression; browser tests separately verify card behavior and accessibility.
