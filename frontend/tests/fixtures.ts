import type { Entity, Hass } from "../src/types";
export function syntheticHass(): Hass {
  const states: Record<string, Entity> = {};
  const add = (
    key: string,
    state: string,
    attrs: Record<string, unknown> = {},
    gas = false,
  ) => {
    const id = `sensor.demo_${key}${gas ? "_gas" : ""}`;
    states[id] = {
      entity_id: id,
      state,
      attributes: {
        globird_sensor_key: key,
        account_id: "demo-account",
        account_service_id: gas ? "gas-demo" : "electric-demo",
        service_type: gas ? "Gas" : "Electricity",
        ...attrs,
      },
    };
  };
  const days = [
    { readDate: "2030/04/29", usage: 4 },
    { readDate: "2030/04/30", usage: 0 },
  ];
  add("usage_total", "4", {
    unit_of_measurement: "kWh",
    days: 2,
    daily: days,
    latest_day: "2030/04/30",
    statistic_id: "globird:demo_import",
  });
  add("solar_export_total", "11", {
    unit_of_measurement: "kWh",
    days: 2,
    daily: [
      { readDate: "2030/04/29", usage: 6 },
      { readDate: "2030/04/30", usage: 5 },
    ],
    latest_day: "2030/04/30",
    statistic_id: "globird:demo_export",
  });
  add("controlled_load_total", "3", {
    unit_of_measurement: "kWh",
    daily: [{ readDate: "2030/04/29", usage: 3 }],
    statistic_id: "globird:demo_controlled",
  });
  add("cost_total", "-1.25", {
    unit_of_measurement: "AUD",
    days: 2,
    latest_day: "2030/04/30",
    daily_totals: [
      { date: "2030/04/29", amount: -1.75 },
      { date: "2030/04/30", amount: 0.5 },
    ],
    incomplete_days: [],
    statistic_id: "globird:demo_cost",
  });
  add("latest_day_usage", "0", {
    latest_day: "2030/04/30",
    unit_of_measurement: "kWh",
  });
  add("latest_day_solar_export", "5", {
    latest_day: "2030/04/30",
    unit_of_measurement: "kWh",
  });
  add("latest_day_controlled_load", "unknown", {
    latest_day: "2030/04/29",
    unit_of_measurement: "kWh",
  });
  add("latest_day_cost", "0.5", {
    latest_day: "2030/04/30",
    unit_of_measurement: "AUD",
  });
  add("expected_month_cost", "15", {
    billing_period_start: "2030/04/28",
    cost_to_date: 1,
    completed_days: 2,
    period_days: 30,
    latest_day: "2030/04/30",
    unit_of_measurement: "AUD",
  });
  add("billing_period_cost", "1", {
    billing_period_start: "2030/04/28",
    unit_of_measurement: "AUD",
  });
  add("latest_data_status", "ready");
  add(
    "latest_gas_reading",
    "unknown",
    { unit_of_measurement: "m³", latest_reading_date: null },
    true,
  );
  add("latest_data_status", "no_data", {}, true);
  add("cost_total", "0", { days: 0, daily_totals: [] }, true);
  const global = (
    key: string,
    state: string,
    attrs: Record<string, unknown>,
  ) => {
    const id = `sensor.demo_${key}`;
    states[id] = {
      entity_id: id,
      state,
      attributes: { globird_sensor_key: key, ...attrs },
    };
  };
  global("dashboard_balance", "-18.5", {
    account_id: "demo-account",
    unit_of_measurement: "AUD",
    latest_invoice: {
      amount: 12.75,
      issuedDate: "2030/04/15",
      dueDate: "2030/05/05",
    },
  });
  global("refresh_status", "ok", {
    last_successful_refresh: "2030-05-01T00:00:00Z",
  });
  global("last_successful_refresh", "2030-05-01T00:00:00Z", {});
  return {
    states,
    locale: { language: "en-AU", number_format: "language" },
    config: { time_zone: "Australia/Brisbane" },
  };
}
