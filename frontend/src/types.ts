export interface Entity {
  entity_id: string;
  state: string;
  attributes: Record<string, unknown>;
}
export interface Hass {
  states: Record<string, Entity>;
  locale?: { language?: string; number_format?: string };
  config: { time_zone: string };
  callWS?: <T>(request: Record<string, unknown>) => Promise<T>;
}
export interface CardConfig {
  type: string;
  entity?: string;
  title?: string;
  default_service_type?: "electricity" | "gas";
  history_source?: "attributes" | "statistics";
  history_days?: number;
}
export interface Service {
  id: string;
  accountId: string;
  type: "electricity" | "gas";
  entities: Record<string, Entity>;
}
export interface DayRow {
  day: string;
  usage?: number;
  cost?: number;
  export?: number;
  controlled?: number;
  incomplete?: boolean;
}
export type Statistics = Record<
  string,
  { start: number; change?: number | null }[]
>;
