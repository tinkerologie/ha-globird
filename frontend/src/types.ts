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
  show_temperature?: boolean;
}
export interface Service {
  id: string;
  accountId: string;
  type: "electricity" | "gas";
  entities: Record<string, Entity>;
  /** Per-register usage sensors (time-of-use windows), keyed by register key. */
  registers?: Record<string, Entity>;
}
/** A breakdown series: one register or one charge category. */
export interface Series {
  key: string;
  label: string;
  /** Import registers and charges stack above zero, exports and credits below. */
  direction: "import" | "export";
  /** Tracking rows re-report energy another register counts; never stacked. */
  tracking?: boolean;
  statisticId?: string;
}
export interface DayRow {
  day: string;
  usage?: number;
  cost?: number;
  export?: number;
  controlled?: number;
  incomplete?: boolean;
  /** Daily kWh per register key. */
  registers?: Record<string, number>;
  /** Daily AUD per charge category. */
  categories?: Record<string, number>;
  tempMin?: number;
  tempMax?: number;
}
export type Statistics = Record<
  string,
  { start: number; change?: number | null }[]
>;
