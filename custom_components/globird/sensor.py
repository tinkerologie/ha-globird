"""Sensor entities for GloBird."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from datetime import time as dt_time
from inspect import isawaitable
from typing import Any

from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    UnitOfEnergy,
    UnitOfTemperature,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_point_in_time
from homeassistant.helpers.start import async_at_started
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import EnergyConverter, VolumeConverter

from .client import (
    ATTR_RECENT_ROW_LIMIT,
    USAGE_CLASS_CONTROLLED_LOAD,
    build_billing_period_projection,
    build_latest_data_status,
    cost_attributes,
    service_id,
    usage_attributes,
)
from .const import DOMAIN
from .coordinator import GloBirdCoordinator

PARALLEL_UPDATES = 0

CURRENCY_AUD = "AUD"
_LOGGER = logging.getLogger(__name__)
ZEROHERO_STATUS_OPTIONS: list[str] = [
    "achieved",
    "missed",
    "pending",
    "awaiting_result",
    "unknown",
]
ZEROHERO_RESULT_CUTOFF = dt_time(hour=21)
# Earliest time searched for stored statistics rows.
STATISTICS_EPOCH = datetime(2000, 1, 1, tzinfo=UTC)
# Longest wait for the recorder to commit an import before the next upload.
RECORDER_COMMIT_TIMEOUT = 60


def _latest_data_status(detail: dict[str, Any]) -> dict[str, Any]:
    """Return cached or computed latest data readiness."""
    status = detail.get("latest_data_status")
    if isinstance(status, dict):
        return status
    return build_latest_data_status(
        detail.get("usage_summary") or {},
        detail.get("cost_summary") or {},
    )


def _payload_data(payload: dict[str, Any] | None) -> Any:
    """Return a standard GloBird payload's data object."""
    if isinstance(payload, dict):
        return payload.get("data")
    return None


def _latest_invoice(data: dict[str, Any]) -> dict[str, Any] | None:
    """Return the latest invoice from the dashboard payload."""
    dashboard_data = _payload_data(data.get("dashboard")) or {}
    invoice = dashboard_data.get("lastestInvoice")
    return invoice if isinstance(invoice, dict) else None


def _recent_transactions(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Return recent dashboard transactions."""
    dashboard_data = _payload_data(data.get("dashboard")) or {}
    transactions = dashboard_data.get("recentAccountTransactions") or []
    return transactions[:10] if isinstance(transactions, list) else []


def _balance_value(data: dict[str, Any]) -> Any:
    summary = data.get("global_summary") or {}
    if "balance" in summary:
        return summary.get("balance")
    balance = _payload_data(data.get("balance")) or {}
    val = balance.get("balance")
    # GloBird returns positive for credit; negate so credit=negative, debt=positive
    return -val if val is not None else None


def _balance_attrs(data: dict[str, Any]) -> dict[str, Any]:
    summary = data.get("global_summary") or {}
    if summary:
        return {
            "max_refundable_amount": summary.get("max_refundable_amount"),
            "show_refundable_amount": summary.get("show_refundable_amount"),
        }
    balance = _payload_data(data.get("balance")) or {}
    return {
        "max_refundable_amount": balance.get("maxRefundableAmount"),
        "show_refundable_amount": balance.get("showRefundableAmount"),
    }


def _dashboard_balance_value(data: dict[str, Any]) -> Any:
    summary = data.get("global_summary") or {}
    if "dashboard_balance" in summary:
        return summary.get("dashboard_balance")
    dashboard = _payload_data(data.get("dashboard")) or {}
    val = dashboard.get("currentBalance")
    return -val if val is not None else None


def _dashboard_attrs(data: dict[str, Any]) -> dict[str, Any]:
    summary = data.get("global_summary") or {}
    dashboard_summary = summary.get("dashboard") if isinstance(summary, dict) else None
    if isinstance(dashboard_summary, dict):
        return dict(dashboard_summary)
    dashboard = _payload_data(data.get("dashboard")) or {}
    return {
        "account_id": dashboard.get("accountId"),
        "account_number": dashboard.get("accountNumber"),
        "latest_correspondence": dashboard.get("lastestCorrespondence"),
        "latest_invoice": dashboard.get("lastestInvoice"),
        "recent_transactions": _recent_transactions(data),
    }


def _latest_invoice_value(data: dict[str, Any]) -> Any:
    summary = data.get("global_summary") or {}
    if "latest_invoice_amount" in summary:
        return summary.get("latest_invoice_amount")
    invoice = _latest_invoice(data)
    return invoice.get("amount") if invoice else None


def _latest_invoice_attrs(data: dict[str, Any]) -> dict[str, Any]:
    summary = data.get("global_summary") or {}
    if isinstance(summary.get("latest_invoice"), dict):
        return dict(summary.get("latest_invoice") or {})
    return dict(_latest_invoice(data) or {})


def _signup_services_value(data: dict[str, Any]) -> int:
    summary = data.get("global_summary") or {}
    if isinstance(summary.get("signup_services"), int):
        return summary.get("signup_services", 0)
    signup = _payload_data(data.get("signup_info"))
    return len(signup) if isinstance(signup, list) else 0


def _signup_services_attrs(data: dict[str, Any]) -> dict[str, Any]:
    summary = data.get("global_summary") or {}
    if isinstance(summary.get("signup_info"), list):
        return {"signup_info": summary.get("signup_info", [])}
    return {"signup_info": _payload_data(data.get("signup_info")) or []}


def _timestamp_value(value: Any) -> datetime | None:
    """Return a Home Assistant timestamp value from a unix timestamp."""
    if value is None:
        return None
    try:
        return datetime.fromtimestamp(float(value), UTC)
    except TypeError, ValueError, OSError:
        return None


def _last_successful_refresh_value(data: dict[str, Any]) -> datetime | None:
    return _timestamp_value(data.get("last_update"))


def _timestamp_attr(value: Any) -> str | None:
    timestamp = _timestamp_value(value)
    return timestamp.isoformat() if timestamp else None


def _local_today() -> date:
    """Return today's date in Home Assistant's configured timezone."""
    return dt_util.now().date()


def _parse_portal_day(value: Any) -> date | None:
    """Parse a portal day string into a date."""
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    for separator in ("T", " "):
        raw = raw.split(separator, 1)[0]
    try:
        return date.fromisoformat(raw.replace("/", "-"))
    except ValueError:
        return None


def _day_reset_timestamp(value: Any) -> datetime | None:
    """Return midnight in local timezone for a portal day string (used for last_reset)."""
    parsed = _parse_portal_day(value)
    if parsed is None:
        return None
    tzinfo = dt_util.now().tzinfo or UTC
    return datetime.combine(parsed, dt_time.min, tzinfo=tzinfo)


def _billing_period_completed_days(
    data: dict[str, Any],
    today: date | None = None,
) -> int | None:
    """Return completed billing-period days using the local HA date."""
    start = _billing_period_start(data)
    if start is None:
        return None
    return max(0, ((today or _local_today()) - start).days)


def _service_type(service: dict[str, Any]) -> str:
    """Return a normalized service type."""
    return str(service.get("serviceType") or "").strip().lower()


def _is_gas_service(service: dict[str, Any]) -> bool:
    """Return whether a service is gas."""
    return "gas" in _service_type(service)


def _service_name_suffix(service: dict[str, Any]) -> str:
    """Return a readable label that distinguishes services in sensor names."""
    site_identifier = str(service.get("siteIdentifier") or "").strip()
    account_service_id = str(service.get("accountServiceId") or "").strip()

    if site_identifier:
        return site_identifier
    if account_service_id:
        return account_service_id
    return account_service_id or "unknown"


def _safe_statistic_id(raw_id: Any, fallback: str) -> str:
    """Return a recorder-safe statistic ID suffix.

    Home Assistant recorder rejects statistic IDs with unsupported characters.
    """
    raw = str(raw_id or fallback).strip().lower()
    safe = re.sub(r"[^a-z0-9_]+", "_", raw).strip("_")
    if not safe:
        safe = re.sub(r"[^a-z0-9_]+", "_", fallback.lower()).strip("_")
    if not safe:
        return "service"
    # Recorder rejects IDs containing double underscores.
    safe = re.sub(r"_+", "_", safe)
    if not safe[0].isalpha():
        safe = f"svc_{safe}"
    return safe.strip("_") or "service"


def _build_gas_statistics(
    history_rows: list[dict[str, Any]],
    *,
    tzinfo: Any,
    stored_before: tuple[float, float] | None = None,
) -> list[StatisticData]:
    """Build serial-aware cumulative gas statistics.

    ``state`` is the meter read index; ``sum`` is the gas used since the first
    read. The first read is a baseline, so ``sum`` starts at 0.0: Home
    Assistant's recorder treats the first-ever row's ``sum`` as consumption
    (change is computed against 0), so starting at the meter index would show
    the whole index as used on the first read day.

    The portal only returns reads from a rolling window, so older reads drop
    out of ``history_rows`` while their rows stay in the recorder.
    ``stored_before`` is the ``(state, sum)`` of the last stored row before the
    first row here. When given, the sum continues from it instead of
    restarting at 0.0, so a rewritten first row never drops below the stored
    row before it. The stored row has no serial, so the first row here is
    treated as the same meter: a lower index adds no usage.

    A replacement meter may restart at a lower index. Keep an independent
    high-water mark for each serial so the cumulative sum continues without
    discarding usage from the replacement meter. A serial's first read is its
    baseline and adds no usage.
    """
    rows = sorted(
        (
            row
            for row in history_rows
            if isinstance(row, dict)
            and _parse_portal_day(row.get("date")) is not None
            and isinstance(row.get("read_index"), (int, float))
        ),
        key=lambda row: (
            str(row.get("date") or ""),
            str(row.get("serial") or ""),
            float(row.get("read_index") or 0.0),
        ),
    )
    if not rows:
        return []

    meter_high_water: dict[str, float] = {}
    cumulative_sum: float | None = None
    by_day: dict[date, StatisticData] = {}

    for row in rows:
        parsed_day = _parse_portal_day(row.get("date"))
        if parsed_day is None:
            continue
        reading = float(row["read_index"])
        meter_key = str(row.get("serial") or "unknown")
        previous = meter_high_water.get(meter_key)

        if cumulative_sum is None:
            cumulative_sum = 0.0
            if stored_before is not None:
                stored_state, stored_sum = stored_before
                cumulative_sum = stored_sum + max(0.0, reading - stored_state)
        elif previous is not None and reading > previous:
            cumulative_sum += reading - previous

        meter_high_water[meter_key] = (
            reading if previous is None else max(previous, reading)
        )
        by_day[parsed_day] = StatisticData(
            start=datetime.combine(parsed_day, dt_time.min, tzinfo=tzinfo),
            state=reading,
            sum=cumulative_sum,
        )

    return [by_day[day] for day in sorted(by_day)]


def _rebase_legacy_gas_rows(stored_rows: list[StatisticData]) -> list[StatisticData]:
    """Return stored gas rows with a legacy meter-index offset removed.

    Releases up to 2026.10.2 started the gas sum at the first meter index, so
    the oldest stored row has ``sum == state``. Rows the portal no longer
    returns are not imported again, so subtract that index from every stored
    row once. Returns an empty list when the rows have no legacy offset; after
    the rebase the oldest row's sum is 0, so this runs only once.
    """
    if not stored_rows:
        return []
    offset = stored_rows[0].get("sum")
    if not offset or offset != stored_rows[0].get("state"):
        return []
    return [
        StatisticData(
            start=row["start"],
            state=row.get("state") or 0.0,
            sum=(row.get("sum") or 0.0) - offset,
        )
        for row in stored_rows
    ]


def _build_daily_cumulative_statistics(
    daily_rows: list[dict[str, Any]],
    *,
    date_key: str,
    value_key: str,
    tzinfo: Any,
    stored_sum: float | None = None,
) -> list[StatisticData]:
    """Build cumulative daily statistics for Energy Dashboard consumption or cost.

    ``state`` is the day's value and ``sum`` the running total. The portal
    only returns a rolling window of days, so ``stored_sum`` is the ``sum``
    of the last stored row before the first day here: the running total
    continues from it instead of restarting when the window moves past the
    oldest day. Without it the first row's ``sum`` is its own day value, so
    first-day usage still counts on the first import. Rows that are already
    wrong outside the window are not repaired.
    """
    by_day: dict[date, float] = {}
    for row in daily_rows:
        if not isinstance(row, dict):
            continue
        parsed_day = _parse_portal_day(row.get(date_key))
        raw_val = row.get(value_key)
        if parsed_day is None or not isinstance(raw_val, (int, float)):
            continue
        by_day[parsed_day] = by_day.get(parsed_day, 0.0) + float(raw_val)

    if not by_day:
        return []

    cumulative_sum = stored_sum or 0.0
    result: list[StatisticData] = []
    for day in sorted(by_day):
        day_value = round(by_day[day], 3)
        cumulative_sum = round(cumulative_sum + day_value, 3)
        result.append(
            StatisticData(
                start=datetime.combine(day, dt_time.min, tzinfo=tzinfo),
                state=day_value,
                sum=cumulative_sum,
            )
        )
    return result


def _zerohero_last_result(
    summary: dict[str, Any],
) -> tuple[str, date | None, str | None]:
    """Return the latest complete ZEROHERO result regardless of local day."""
    latest_day_raw = summary.get("latest_day")
    latest_day = _parse_portal_day(latest_day_raw)
    credit = summary.get("latest_day_zerohero_credit")
    if latest_day is None or credit is None:
        return "unknown", latest_day, latest_day_raw
    result = "achieved" if summary.get("latest_day_zerohero_achieved") else "missed"
    return result, latest_day, latest_day_raw


def _zerohero_status(
    summary: dict[str, Any],
    now: datetime | None = None,
) -> str:
    """Return the latest complete ZEROHERO portal result."""
    last_result, latest_day, _latest_day_raw = _zerohero_last_result(summary)
    if last_result == "unknown" or latest_day is None:
        return "unknown"
    return last_result


def _next_zerohero_status_boundary(now: datetime) -> datetime:
    """Return the next local boundary where ZEROHERO status can change."""
    today_cutoff = datetime.combine(
        now.date(),
        ZEROHERO_RESULT_CUTOFF,
        tzinfo=now.tzinfo,
    )
    if now < today_cutoff:
        return today_cutoff
    return datetime.combine(
        now.date() + timedelta(days=1),
        dt_time.min,
        tzinfo=now.tzinfo,
    )


def _refresh_status_value(data: dict[str, Any]) -> str:
    summary = data.get("global_summary") or {}
    if isinstance(summary.get("refresh_status"), str):
        return summary.get("refresh_status", "ok")
    return "error" if data.get("refresh_error") else "ok"


def _refresh_status_attrs(data: dict[str, Any]) -> dict[str, Any]:
    summary = data.get("global_summary") or {}
    if summary:
        return {
            "last_successful_refresh": _timestamp_attr(
                summary.get("last_successful_refresh")
            ),
            "last_failed_refresh": _timestamp_attr(summary.get("last_failed_refresh")),
            "refresh_error": summary.get("refresh_error"),
            "fetch_errors": summary.get("fetch_errors") or {},
        }
    return {
        "last_successful_refresh": _timestamp_attr(data.get("last_update")),
        "last_failed_refresh": _timestamp_attr(data.get("last_failed_update")),
        "refresh_error": data.get("refresh_error"),
        "fetch_errors": data.get("_fetch_errors") or {},
    }


@dataclass(frozen=True)
class GloBirdSensorDescription:
    """Description for a GloBird sensor."""

    key: str
    name: str
    value_fn: Callable[[dict[str, Any]], Any]
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any]] | None = None
    native_unit_of_measurement: str | None = None
    device_class: SensorDeviceClass | None = None
    state_class: SensorStateClass | None = None
    entity_category: EntityCategory | None = None
    icon: str | None = None


GLOBAL_SENSORS: tuple[GloBirdSensorDescription, ...] = (
    GloBirdSensorDescription(
        key="balance",
        name="Balance",
        value_fn=_balance_value,
        attrs_fn=_balance_attrs,
        native_unit_of_measurement=CURRENCY_AUD,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:cash",
    ),
    GloBirdSensorDescription(
        key="dashboard_balance",
        name="Dashboard Balance",
        value_fn=_dashboard_balance_value,
        attrs_fn=_dashboard_attrs,
        native_unit_of_measurement=CURRENCY_AUD,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
        icon="mdi:view-dashboard",
    ),
    GloBirdSensorDescription(
        key="latest_invoice",
        name="Latest Invoice",
        value_fn=_latest_invoice_value,
        attrs_fn=_latest_invoice_attrs,
        native_unit_of_measurement=CURRENCY_AUD,
        device_class=SensorDeviceClass.MONETARY,
        icon="mdi:file-document",
    ),
    GloBirdSensorDescription(
        key="signup_services",
        name="Signup Services",
        value_fn=_signup_services_value,
        attrs_fn=_signup_services_attrs,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:transmission-tower",
    ),
    GloBirdSensorDescription(
        key="last_successful_refresh",
        name="Last Successful Refresh",
        value_fn=_last_successful_refresh_value,
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:update",
    ),
    GloBirdSensorDescription(
        key="refresh_status",
        name="Refresh Status",
        value_fn=_refresh_status_value,
        attrs_fn=_refresh_status_attrs,
        entity_category=EntityCategory.DIAGNOSTIC,
        icon="mdi:cloud-refresh",
    ),
)


def _create_background_upload(
    entity: GloBirdBaseSensor,
    upload: Coroutine[Any, Any, None],
    kind: str,
) -> None:
    """Start a statistics upload that Home Assistant does not wait for.

    The task belongs to the config entry, so unloading or reloading the
    entry cancels it before a new entity can start its own upload.
    """
    entity._config_entry.async_create_background_task(
        entity.hass, upload, f"globird {kind} upload {entity.entity_id}"
    )


def _register_unique_id(config_entry: ConfigEntry, sid: str, slug: str) -> str:
    """Return the unique ID of a per-register usage sensor."""
    return f"{config_entry.entry_id}_service_{sid}_register_{slug}"


def _dynamic_usage_entities(
    coordinator: GloBirdCoordinator,
    config_entry: ConfigEntry,
    known_unique_ids: set[str],
) -> list[SensorEntity]:
    """Return usage sensors for registers the portal returns that are new.

    Controlled-load sensors exist only for services with controlled-load
    registers, and register sensors only for registers flagged
    ``register_sensor``. ``known_unique_ids`` is updated so a later refresh
    never adds the same entity twice.
    """
    data = coordinator.data or {}
    service_data = data.get("service_data") or {}
    entities: list[SensorEntity] = []
    for service in data.get("services", []):
        if _is_gas_service(service):
            continue
        sid = service_id(service)
        detail = service_data.get(sid)
        summary = (
            detail.get("usage_summary") if isinstance(detail, dict) else None
        ) or {}
        registers = [
            register
            for register in summary.get("registers") or []
            if isinstance(register, dict)
        ]
        candidates: list[GloBirdServiceBaseSensor] = []
        if any(
            register.get("usage_class") == USAGE_CLASS_CONTROLLED_LOAD
            for register in registers
        ):
            candidates.extend(
                [
                    GloBirdControlledLoadTotalSensor(
                        coordinator, config_entry, service
                    ),
                    GloBirdLatestDayControlledLoadSensor(
                        coordinator, config_entry, service
                    ),
                ]
            )
        candidates.extend(
            GloBirdUsageRegisterSensor(coordinator, config_entry, service, register)
            for register in registers
            if register.get("register_sensor")
        )
        for entity in candidates:
            unique_id = str(entity.unique_id)
            if unique_id in known_unique_ids:
                continue
            known_unique_ids.add(unique_id)
            entities.append(entity)
    return entities


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up GloBird sensors from a config entry."""
    coordinator: GloBirdCoordinator = (
        getattr(config_entry, "runtime_data", None)
        or hass.data[DOMAIN][config_entry.entry_id]
    )
    data = coordinator.data or {}

    entities: list[SensorEntity] = [
        GloBirdGlobalSensor(coordinator, config_entry, description)
        for description in GLOBAL_SENSORS
    ]

    for account in data.get("accounts", []):
        entities.append(GloBirdAccountSummarySensor(coordinator, config_entry, account))

    for service in data.get("services", []):
        service_entities: list[SensorEntity] = [
            GloBirdServiceStatusSensor(coordinator, config_entry, service),
            GloBirdMeterInfoSensor(coordinator, config_entry, service),
        ]

        if _is_gas_service(service):
            service_entities.extend(
                [
                    GloBirdLatestDataDateSensor(coordinator, config_entry, service),
                    GloBirdLatestDataStatusSensor(coordinator, config_entry, service),
                    GloBirdLatestGasReadingSensor(coordinator, config_entry, service),
                    GloBirdLatestGasReadingDateSensor(
                        coordinator,
                        config_entry,
                        service,
                    ),
                    GloBirdCostTotalSensor(coordinator, config_entry, service),
                    GloBirdLatestDayCostSensor(coordinator, config_entry, service),
                    GloBirdExpectedMonthlyCostSensor(
                        coordinator,
                        config_entry,
                        service,
                    ),
                    GloBirdBillingPeriodDaysSensor(coordinator, config_entry, service),
                    GloBirdBillingPeriodCostSensor(coordinator, config_entry, service),
                ]
            )
        else:
            service_entities.extend(
                [
                    GloBirdLatestDataDateSensor(coordinator, config_entry, service),
                    GloBirdLatestDataStatusSensor(coordinator, config_entry, service),
                    GloBirdUsageTotalSensor(coordinator, config_entry, service),
                    GloBirdLatestDayUsageSensor(coordinator, config_entry, service),
                    GloBirdSolarExportTotalSensor(coordinator, config_entry, service),
                    GloBirdLatestDaySolarExportSensor(
                        coordinator,
                        config_entry,
                        service,
                    ),
                    GloBirdCostTotalSensor(coordinator, config_entry, service),
                    GloBirdLatestDayCostSensor(coordinator, config_entry, service),
                    GloBirdSolarExportCreditTotalSensor(
                        coordinator,
                        config_entry,
                        service,
                    ),
                    GloBirdLatestDaySolarExportCreditSensor(
                        coordinator,
                        config_entry,
                        service,
                    ),
                    GloBirdZeroHeroStatusSensor(coordinator, config_entry, service),
                    GloBirdExpectedMonthlyCostSensor(
                        coordinator,
                        config_entry,
                        service,
                    ),
                    GloBirdBillingPeriodDaysSensor(coordinator, config_entry, service),
                    GloBirdBillingPeriodCostSensor(coordinator, config_entry, service),
                    GloBirdWeatherSummarySensor(coordinator, config_entry, service),
                ]
            )

        entities.extend(service_entities)

    # Usage sensors that depend on the registers the portal returns. Plans
    # can add registers later, so check again after every refresh.
    known_unique_ids: set[str] = set()
    entities.extend(
        _dynamic_usage_entities(coordinator, config_entry, known_unique_ids)
    )
    async_add_entities(entities)

    @callback
    def _async_add_new_usage_entities() -> None:
        new_entities = _dynamic_usage_entities(
            coordinator, config_entry, known_unique_ids
        )
        if new_entities:
            async_add_entities(new_entities)

    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_add_new_usage_entities)
    )


class GloBirdBaseSensor(CoordinatorEntity[GloBirdCoordinator], SensorEntity):
    """Base class for GloBird sensors."""

    _attr_has_entity_name = True
    _unrecorded_attributes = frozenset({"globird_sensor_key", "statistic_id"})

    def __init__(
        self, coordinator: GloBirdCoordinator, config_entry: ConfigEntry
    ) -> None:
        """Initialize the base sensor."""
        super().__init__(coordinator)
        self._config_entry = config_entry


class GloBirdGlobalSensor(GloBirdBaseSensor):
    """A config-entry level GloBird sensor."""

    def __init__(
        self,
        coordinator: GloBirdCoordinator,
        config_entry: ConfigEntry,
        description: GloBirdSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry)
        self._description = description
        self._attr_translation_key = description.key
        self._attr_name = description.name
        self._attr_unique_id = f"{config_entry.entry_id}_{description.key}"
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_entity_category = description.entity_category
        self._attr_icon = description.icon
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": "GloBird Energy",
            "manufacturer": "GloBird Energy",
            "model": "Customer Portal",
        }

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        return self._description.value_fn(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return sensor attributes."""
        attrs_fn = self._description.attrs_fn
        attrs = attrs_fn(self.coordinator.data or {}) if attrs_fn else {}
        return {**attrs, "globird_sensor_key": self._description.key}


class GloBirdAccountSummarySensor(GloBirdBaseSensor):
    """Summary sensor for a GloBird account."""

    def __init__(
        self,
        coordinator: GloBirdCoordinator,
        config_entry: ConfigEntry,
        account: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry)
        self._account_id = str(account.get("accountId") or account.get("accountNumber"))
        self._attr_translation_key = "account_summary"
        self._attr_name = f"Account {account.get('accountNumber') or self._account_id}"
        self._attr_icon = "mdi:account"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_unique_id = (
            f"{config_entry.entry_id}_account_{self._account_id}_summary"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": "GloBird Energy",
            "manufacturer": "GloBird Energy",
            "model": "Customer Portal",
        }

    def _account(self) -> dict[str, Any]:
        """Return the latest account row."""
        for account in (self.coordinator.data or {}).get("accounts", []):
            account_id = str(account.get("accountId") or account.get("accountNumber"))
            if account_id == self._account_id:
                return account
        return {}

    @property
    def native_value(self) -> Any:
        """Return account service count."""
        return self._account().get("service_count")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return account attributes."""
        return {**self._account(), "globird_sensor_key": "account_summary"}


class GloBirdServiceBaseSensor(GloBirdBaseSensor):
    """Base class for service-level sensors."""

    sensor_key: str = "service"
    sensor_name: str = "Service"
    sensor_icon: str | None = "mdi:flash"
    sensor_unit: str | None = None
    sensor_device_class: SensorDeviceClass | None = None
    sensor_state_class: SensorStateClass | None = None
    sensor_entity_category: EntityCategory | None = None

    def __init__(
        self,
        coordinator: GloBirdCoordinator,
        config_entry: ConfigEntry,
        service: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry)
        self._service_id = service_id(service)
        self._attr_translation_key = self.sensor_key
        if _is_gas_service(service):
            self._attr_name = f"{self.sensor_name} ({_service_name_suffix(service)})"
        else:
            self._attr_name = self.sensor_name
        self._attr_unique_id = (
            f"{config_entry.entry_id}_service_{self._service_id}_{self.sensor_key}"
        )
        self._attr_icon = self.sensor_icon
        self._attr_native_unit_of_measurement = self.sensor_unit
        self._attr_device_class = self.sensor_device_class
        self._attr_state_class = self.sensor_state_class
        self._attr_entity_category = self.sensor_entity_category
        self._attr_device_info = {
            "identifiers": {(DOMAIN, config_entry.entry_id)},
            "name": "GloBird Energy",
            "manufacturer": "GloBird Energy",
            "model": "Customer Portal",
        }

    def _service_detail(self) -> dict[str, Any]:
        """Return the latest service detail."""
        service_data = (self.coordinator.data or {}).get("service_data", {})
        detail = service_data.get(self._service_id)
        return detail if isinstance(detail, dict) else {}

    def _service_attrs(self) -> dict[str, Any]:
        """Return service metadata attributes."""
        detail = self._service_detail()
        service = detail.get("service") or {}
        attrs = {
            "globird_sensor_key": (
                "register" if self.sensor_key == "usage_register" else self.sensor_key
            ),
            "account_service_id": service.get("accountServiceId"),
            "site_identifier": service.get("siteIdentifier"),
            "site_address": service.get("siteAddress"),
            "post_code": service.get("postCode"),
            "service_type": service.get("serviceType"),
            "account_id": service.get("accountId"),
            "account_number": service.get("accountNumber"),
        }
        if isinstance(
            self, (GloBirdDailyStatisticsSensor, GloBirdLatestGasReadingSensor)
        ):
            attrs["statistic_id"] = self._external_statistic_id()
        return attrs

    def _external_statistic_id(self) -> str:
        """Return the exact identifier used by the existing statistics importer."""
        suffix = _safe_statistic_id(
            getattr(self, "_attr_unique_id", self._service_id), self._service_id
        )
        return f"{DOMAIN}:{suffix}"

    async def _async_stored_rows_before(
        self, statistic_id: str, before: datetime, types: set[str]
    ) -> list[StatisticData]:
        """Return the stored statistic rows that start before ``before``.

        The portal only returns a rolling window, so rows older than the
        window are no longer imported and the next upload must continue from
        the last of them. ``types`` are the statistic columns a row needs
        (``sum``, and ``state`` for gas); rows missing one are left out.
        Exceptions are not caught: each caller skips its import instead.
        """
        from homeassistant.components.recorder.statistics import (
            statistics_during_period,
        )
        from homeassistant.helpers.recorder import get_instance

        stored = await get_instance(self.hass).async_add_executor_job(
            statistics_during_period,
            self.hass,
            STATISTICS_EPOCH,
            before,
            {statistic_id},
            "hour",
            None,
            types,
        )
        rows: list[StatisticData] = []
        for row in stored.get(statistic_id) or []:
            start = row.get("start")
            total = row.get("sum")
            state = row.get("state")
            if start is None or total is None or ("state" in types and state is None):
                continue
            item = StatisticData(
                start=datetime.fromtimestamp(float(start), UTC),
                sum=float(total),
            )
            if state is not None and "state" in types:
                item["state"] = float(state)
            rows.append(item)
        return rows

    async def _async_upload_daily_external_statistics(
        self,
        daily_rows: list[dict[str, Any]],
        *,
        date_key: str,
        value_key: str,
        unit_class: str | None,
    ) -> None:
        """Upload daily cumulative external statistics for the Home Assistant Energy Dashboard."""
        if not isinstance(daily_rows, list) or not daily_rows:
            return

        try:
            from homeassistant.components.recorder.statistics import (
                async_add_external_statistics,
            )
        except ImportError:
            return

        statistic_id = self._external_statistic_id()
        tzinfo = dt_util.now().tzinfo or UTC
        statistics = _build_daily_cumulative_statistics(
            daily_rows,
            date_key=date_key,
            value_key=value_key,
            tzinfo=tzinfo,
        )
        if not statistics:
            return

        try:
            stored_rows = await self._async_stored_rows_before(
                statistic_id, statistics[0]["start"], {"sum"}
            )
        except Exception as err:
            # Never rewrite stored rows without knowing where the sum must
            # continue from; retry on the next coordinator update.
            _LOGGER.warning(
                "GloBird external statistics import skipped for %s (%s): could not read stored statistics: %s",
                self._service_id,
                statistic_id,
                err,
            )
            return
        if stored_rows:
            statistics = _build_daily_cumulative_statistics(
                daily_rows,
                date_key=date_key,
                value_key=value_key,
                tzinfo=tzinfo,
                stored_sum=stored_rows[-1].get("sum"),
            )

        metadata = StatisticMetaData(
            has_mean=False,
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name=self._attr_name,
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_class=unit_class,
            unit_of_measurement=self._attr_native_unit_of_measurement,
        )
        try:
            add_result: Any = async_add_external_statistics(
                self.hass, metadata, statistics
            )
            if isawaitable(add_result):
                await add_result
        except Exception as err:
            _LOGGER.warning(
                "GloBird external statistics import skipped for %s (%s): %s",
                self._service_id,
                statistic_id,
                err,
            )
            return
        await self._async_wait_for_statistics_commit(statistic_id)

    async def _async_wait_for_statistics_commit(self, statistic_id: str) -> None:
        """Wait until the recorder has committed the queued statistics import.

        ``async_add_external_statistics`` only queues an import task. The
        recorder runs its queue in order, and a commit future resolves once
        every task queued before it has run and been committed, so the next
        upload's stored-row lookup sees these rows. An import the recorder
        queues again after a database error runs after the future; the next
        refresh uploads the window again. The wait is bounded so a stuck
        recorder cannot hold the upload lock forever.
        """
        from homeassistant.helpers.recorder import get_instance

        try:
            future = get_instance(self.hass).async_get_commit_future()
            if future is not None:
                async with asyncio.timeout(RECORDER_COMMIT_TIMEOUT):
                    await future
        except Exception as err:
            _LOGGER.debug(
                "GloBird statistics import for %s (%s) not confirmed as committed: %r",
                self._service_id,
                statistic_id,
                err,
            )


class GloBirdDailyStatisticsSensor(GloBirdServiceBaseSensor):
    """Service sensor that imports a daily series as external statistics.

    The series is uploaded when the entity is added and after every
    coordinator update. Subclasses implement ``_async_upload_statistics``.
    Uploads of one entity run one at a time, so reading the stored row that
    anchors the sum and writing the new rows cannot interleave with another
    upload.
    """

    def __init__(
        self,
        coordinator: GloBirdCoordinator,
        config_entry: ConfigEntry,
        service: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, service)
        self._statistics_lock = asyncio.Lock()

    async def async_added_to_hass(self) -> None:
        """Upload the daily series once Home Assistant has started."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_at_started(self.hass, self._async_start_statistics_upload)
        )

    @callback
    def _async_start_statistics_upload(self, _hass: HomeAssistant) -> None:
        """Run the first upload in the background.

        The upload waits for recorder commits, and the recorder does not
        commit until Home Assistant has started, so it must never run inside
        entity setup.
        """
        _create_background_upload(
            self, self._async_upload_statistics_serialised(), "daily statistics"
        )

    def _handle_coordinator_update(self) -> None:
        """Refresh the entity and import newly published statistics."""
        super()._handle_coordinator_update()
        if hasattr(self.hass, "async_create_task"):
            self.hass.async_create_task(self._async_upload_statistics_serialised())

    async def _async_upload_statistics_serialised(self) -> None:
        """Upload the daily series after any earlier upload has finished."""
        async with self._statistics_lock:
            await self._async_upload_statistics()

    async def _async_upload_statistics(self) -> None:
        """Upload this sensor's daily series."""
        raise NotImplementedError


class GloBirdServiceStatusSensor(GloBirdServiceBaseSensor):
    """Service status sensor."""

    sensor_key = "service_status"
    sensor_name = "Service Status"
    sensor_icon = "mdi:transmission-tower"
    sensor_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> Any:
        """Return service status."""
        detail = self._service_detail()
        status = detail.get("status") or {}
        service = detail.get("service") or {}
        return status.get("status") or service.get("status")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return service status attributes."""
        attrs = self._service_attrs()
        attrs["status_detail"] = self._service_detail().get("status")
        return attrs


class GloBirdMeterInfoSensor(GloBirdServiceBaseSensor):
    """Meter info sensor."""

    sensor_key = "meter_info"
    sensor_name = "Meter Info"
    sensor_icon = "mdi:counter"
    sensor_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> Any:
        """Return meter read type."""
        meter = self._service_detail().get("meter") or {}
        return meter.get("meterReadType") or meter.get("serialStatus")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return meter attributes."""
        attrs = self._service_attrs()
        attrs["meter"] = self._service_detail().get("meter")
        return attrs


class GloBirdLatestDataDateSensor(GloBirdServiceBaseSensor):
    """Latest service data date ready for daily automations."""

    sensor_key = "latest_data_date"
    sensor_name = "Latest Data Date"
    sensor_icon = "mdi:calendar-check"
    sensor_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> Any:
        """Return the latest date with aligned usage and cost data."""
        return _latest_data_status(self._service_detail()).get("latest_ready_day")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return latest data status attributes."""
        attrs = self._service_attrs()
        detail = self._service_detail()
        latest_status = _latest_data_status(detail)
        attrs.update(
            {
                "status": latest_status.get("status"),
                "latest_usage_day": latest_status.get("latest_usage_day"),
                "latest_cost_day": latest_status.get("latest_cost_day"),
                "latest_available_cost_day": latest_status.get(
                    "latest_available_cost_day"
                ),
                "latest_available_cost_day_complete": latest_status.get(
                    "latest_available_cost_day_complete"
                ),
                "incomplete_cost_days": latest_status.get("incomplete_cost_days", []),
                "last_successful_refresh": _timestamp_attr(
                    (self.coordinator.data or {}).get("last_update")
                ),
            }
        )
        return attrs


class GloBirdLatestDataStatusSensor(GloBirdServiceBaseSensor):
    """Latest service data readiness status."""

    sensor_key = "latest_data_status"
    sensor_name = "Latest Data Status"
    sensor_icon = "mdi:calendar-sync"
    sensor_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> Any:
        """Return whether the latest service data is ready."""
        return _latest_data_status(self._service_detail()).get("status")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return latest data readiness attributes."""
        attrs = self._service_attrs()
        latest_status = _latest_data_status(self._service_detail())
        attrs.update(
            {
                "latest_ready_day": latest_status.get("latest_ready_day"),
                "latest_usage_day": latest_status.get("latest_usage_day"),
                "latest_cost_day": latest_status.get("latest_cost_day"),
                "latest_available_cost_day": latest_status.get(
                    "latest_available_cost_day"
                ),
                "latest_available_cost_day_complete": latest_status.get(
                    "latest_available_cost_day_complete"
                ),
                "incomplete_cost_days": latest_status.get("incomplete_cost_days", []),
            }
        )
        return attrs


class GloBirdLatestGasReadingSensor(GloBirdServiceBaseSensor):
    """Latest gas meter index reading."""

    sensor_key = "latest_gas_reading"
    sensor_name = "Latest Gas Reading"
    sensor_icon = "mdi:meter-gas"
    sensor_unit = UnitOfVolume.CUBIC_METERS
    sensor_device_class = SensorDeviceClass.GAS
    # No state class: a meter index read every few months cannot produce
    # correct hourly statistics. The imported ``globird:`` external statistic
    # carries the cumulative sum and is the Energy dashboard gas source.
    sensor_state_class = None

    def __init__(
        self,
        coordinator: GloBirdCoordinator,
        config_entry: ConfigEntry,
        service: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, service)
        self._statistics_lock = asyncio.Lock()

    async def async_added_to_hass(self) -> None:
        """Upload historical gas readings once Home Assistant has started."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_at_started(self.hass, self._async_start_statistics_upload)
        )

    @callback
    def _async_start_statistics_upload(self, _hass: HomeAssistant) -> None:
        """Run the first gas history upload in the background."""
        _create_background_upload(
            self, self._async_upload_gas_statistics_serialised(), "gas statistics"
        )

    def _handle_coordinator_update(self) -> None:
        """Refresh the entity and import any newly published gas reads."""
        super()._handle_coordinator_update()
        if hasattr(self.hass, "async_create_task"):
            self.hass.async_create_task(self._async_upload_gas_statistics_serialised())

    async def _async_upload_gas_statistics_serialised(self) -> None:
        """Upload the gas history after any earlier upload has finished."""
        async with self._statistics_lock:
            await self._async_upload_historical_statistics()

    async def _async_upload_historical_statistics(self) -> None:
        """Import all historical gas meter reads as external statistics."""
        summary = self._service_detail().get("gas_reading_summary") or {}
        history_rows = summary.get("history")
        if not isinstance(history_rows, list) or not history_rows:
            _LOGGER.debug(
                "GloBird gas statistics import skipped for %s (%s): no gas history rows available",
                self._service_id,
                getattr(self, "_attr_unique_id", self._service_id),
            )
            return

        try:
            from homeassistant.components.recorder.statistics import (
                async_add_external_statistics,
            )
        except ImportError:
            return

        tzinfo = dt_util.now().tzinfo or UTC
        statistics = _build_gas_statistics(history_rows, tzinfo=tzinfo)

        if not statistics:
            _LOGGER.debug(
                "GloBird gas statistics import skipped for %s (%s): no valid gas statistics rows after parsing",
                self._service_id,
                getattr(self, "_attr_unique_id", self._service_id),
            )
            return

        statistic_id = self._external_statistic_id()
        try:
            stored_rows = await self._async_stored_rows_before(
                statistic_id, statistics[0]["start"], {"state", "sum"}
            )
        except Exception as err:
            # Never rewrite stored rows without knowing where the sum must
            # continue from; retry on the next coordinator update.
            _LOGGER.warning(
                "GloBird gas statistics import skipped for %s (%s): could not read stored statistics: %s",
                self._service_id,
                statistic_id,
                err,
            )
            return
        rebased_rows = _rebase_legacy_gas_rows(stored_rows)
        if rebased_rows:
            _LOGGER.info(
                "GloBird gas statistics for %s (%s): removing the meter index "
                "from %d stored rows imported before the sum started at 0",
                self._service_id,
                statistic_id,
                len(rebased_rows),
            )
            stored_rows = rebased_rows
        if stored_rows:
            last = stored_rows[-1]
            statistics = _build_gas_statistics(
                history_rows,
                tzinfo=tzinfo,
                # The lookup only returns gas rows with a state and a sum.
                stored_before=(last.get("state") or 0.0, last.get("sum") or 0.0),
            )
        statistics = rebased_rows + statistics
        metadata = StatisticMetaData(
            has_mean=False,
            mean_type=StatisticMeanType.NONE,
            has_sum=True,
            name=self._attr_name,
            source=DOMAIN,
            statistic_id=statistic_id,
            unit_class=VolumeConverter.UNIT_CLASS,
            unit_of_measurement=self._attr_native_unit_of_measurement,
        )
        _LOGGER.debug(
            "GloBird gas statistics prepared for %s (%s): %d rows from %s to %s",
            self._service_id,
            statistic_id,
            len(statistics),
            statistics[0]["start"].isoformat(),
            statistics[-1]["start"].isoformat(),
        )
        try:
            add_result: Any = async_add_external_statistics(
                self.hass, metadata, statistics
            )
            if isawaitable(add_result):
                await add_result
        except Exception as err:
            _LOGGER.warning(
                "GloBird gas statistics import skipped for %s (%s): %s",
                self._service_id,
                statistic_id,
                err,
            )
            return
        await self._async_wait_for_statistics_commit(statistic_id)

    @property
    def native_value(self) -> Any:
        """Return latest gas meter read index, or None until the first read."""
        summary = self._service_detail().get("gas_reading_summary") or {}
        return summary.get("latest_reading")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return latest gas reading metadata and compact history."""
        attrs = self._service_attrs()
        summary = self._service_detail().get("gas_reading_summary") or {}
        attrs.update(
            {
                "latest_reading_date": summary.get("latest_reading_date"),
                "latest_reading_source": summary.get("latest_reading_source"),
                "latest_reading_serial": summary.get("latest_reading_serial"),
                "latest_reading_quality_method": summary.get(
                    "latest_reading_quality_method"
                ),
                "history": summary.get("history_recent", []),
                "history_count": summary.get("history_count", 0),
                "history_truncated": summary.get("history_truncated", False),
            }
        )
        return attrs


class GloBirdLatestGasReadingDateSensor(GloBirdServiceBaseSensor):
    """Latest gas meter reading date."""

    sensor_key = "latest_gas_reading_date"
    sensor_name = "Latest Gas Reading Date"
    sensor_icon = "mdi:calendar-clock"
    sensor_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> Any:
        """Return latest gas read date."""
        return (self._service_detail().get("gas_reading_summary") or {}).get(
            "latest_reading_date"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return latest gas read metadata."""
        attrs = self._service_attrs()
        summary = self._service_detail().get("gas_reading_summary") or {}
        attrs.update(
            {
                "latest_reading": summary.get("latest_reading"),
                "latest_reading_source": summary.get("latest_reading_source"),
                "latest_reading_serial": summary.get("latest_reading_serial"),
                "latest_reading_quality_method": summary.get(
                    "latest_reading_quality_method"
                ),
            }
        )
        return attrs


class GloBirdUsageTotalSensor(GloBirdDailyStatisticsSensor):
    """Recent usage total sensor (supports HA Energy Dashboard grid consumption)."""

    sensor_key = "usage_total"
    sensor_name = "Recent Usage Total"
    sensor_icon = "mdi:lightning-bolt"
    sensor_unit = UnitOfEnergy.KILO_WATT_HOUR
    sensor_device_class = SensorDeviceClass.ENERGY
    sensor_state_class = SensorStateClass.TOTAL

    async def _async_upload_statistics(self) -> None:
        """Upload daily electricity import statistics."""
        summary = self._service_detail().get("usage_summary") or {}
        await self._async_upload_daily_external_statistics(
            summary.get("daily") or [],
            date_key="readDate",
            value_key="usage",
            unit_class=EnergyConverter.UNIT_CLASS,
        )

    @property
    def native_value(self) -> Any:
        """Return total recent usage."""
        detail = self._service_detail()
        val = (detail.get("usage_summary") or {}).get("total_usage")
        return val if val is not None else (0.0 if detail else None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return usage summary attributes."""
        attrs = self._service_attrs()
        summary = self._service_detail().get("usage_summary") or {}
        attrs.update(usage_attributes(summary, direction="import"))
        return attrs


class GloBirdLatestDayUsageSensor(GloBirdServiceBaseSensor):
    """Latest day usage sensor (supports HA Energy Dashboard with daily last_reset)."""

    sensor_key = "latest_day_usage"
    sensor_name = "Latest Day Usage"
    sensor_icon = "mdi:calendar-today"
    sensor_unit = UnitOfEnergy.KILO_WATT_HOUR
    sensor_device_class = SensorDeviceClass.ENERGY
    sensor_state_class = SensorStateClass.TOTAL

    @property
    def last_reset(self) -> datetime | None:
        """Return midnight of the latest day so Recorder resets daily totals cleanly."""
        summary = self._service_detail().get("usage_summary") or {}
        return _day_reset_timestamp(summary.get("latest_day"))

    @property
    def native_value(self) -> Any:
        """Return latest day usage."""
        return (self._service_detail().get("usage_summary") or {}).get(
            "latest_day_usage"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return latest interval attributes."""
        attrs = self._service_attrs()
        summary = self._service_detail().get("usage_summary") or {}
        attrs.update(
            usage_attributes(
                summary,
                direction="import",
                include_latest_intervals=True,
            )
        )
        return attrs


class GloBirdSolarExportTotalSensor(GloBirdDailyStatisticsSensor):
    """Recent solar export total sensor (B1 register, supports Energy Dashboard Return to Grid)."""

    sensor_key = "solar_export_total"
    sensor_name = "Recent Solar Export Total"
    sensor_icon = "mdi:solar-power"
    sensor_unit = UnitOfEnergy.KILO_WATT_HOUR
    sensor_device_class = SensorDeviceClass.ENERGY
    sensor_state_class = SensorStateClass.TOTAL

    async def _async_upload_statistics(self) -> None:
        """Upload daily solar export statistics."""
        summary = self._service_detail().get("usage_summary") or {}
        await self._async_upload_daily_external_statistics(
            summary.get("export_daily") or [],
            date_key="readDate",
            value_key="usage",
            unit_class=EnergyConverter.UNIT_CLASS,
        )

    @property
    def native_value(self) -> Any:
        """Return total recent solar export (feed-in)."""
        detail = self._service_detail()
        val = (detail.get("usage_summary") or {}).get("total_export")
        return val if val is not None else (0.0 if detail else None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return solar export summary attributes."""
        attrs = self._service_attrs()
        summary = self._service_detail().get("usage_summary") or {}
        attrs.update(usage_attributes(summary, direction="export"))
        return attrs


class GloBirdLatestDaySolarExportSensor(GloBirdServiceBaseSensor):
    """Latest day solar export sensor (B1 register)."""

    sensor_key = "latest_day_solar_export"
    sensor_name = "Latest Day Solar Export"
    sensor_icon = "mdi:solar-power-variant"
    sensor_unit = UnitOfEnergy.KILO_WATT_HOUR
    sensor_device_class = SensorDeviceClass.ENERGY
    sensor_state_class = SensorStateClass.TOTAL

    @property
    def last_reset(self) -> datetime | None:
        """Return midnight of the latest export day so Recorder resets daily totals cleanly."""
        summary = self._service_detail().get("usage_summary") or {}
        export_daily = summary.get("export_daily") or []
        latest_day = (
            export_daily[-1].get("readDate")
            if export_daily and isinstance(export_daily[-1], dict)
            else summary.get("latest_day")
        )
        return _day_reset_timestamp(latest_day)

    @property
    def native_value(self) -> Any:
        """Return latest day solar export."""
        return (self._service_detail().get("usage_summary") or {}).get(
            "latest_day_export"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return latest day attributes."""
        attrs = self._service_attrs()
        summary = self._service_detail().get("usage_summary") or {}
        attrs.update(usage_attributes(summary, direction="export"))
        return attrs


class GloBirdControlledLoadTotalSensor(GloBirdDailyStatisticsSensor):
    """Recent controlled-load usage total (separately metered off-peak circuit).

    Created only for services that return controlled-load registers.
    """

    sensor_key = "controlled_load_total"
    sensor_name = "Recent Controlled Load Total"
    sensor_icon = "mdi:water-boiler"
    sensor_unit = UnitOfEnergy.KILO_WATT_HOUR
    sensor_device_class = SensorDeviceClass.ENERGY
    sensor_state_class = SensorStateClass.TOTAL

    async def _async_upload_statistics(self) -> None:
        """Upload daily controlled-load statistics."""
        summary = self._service_detail().get("usage_summary") or {}
        await self._async_upload_daily_external_statistics(
            summary.get("controlled_load_daily") or [],
            date_key="readDate",
            value_key="usage",
            unit_class=EnergyConverter.UNIT_CLASS,
        )

    @property
    def native_value(self) -> Any:
        """Return total recent controlled-load usage."""
        detail = self._service_detail()
        val = (detail.get("usage_summary") or {}).get("total_controlled_load")
        return val if val is not None else (0.0 if detail else None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return controlled-load summary attributes."""
        attrs = self._service_attrs()
        summary = self._service_detail().get("usage_summary") or {}
        attrs.update(usage_attributes(summary, direction="controlled_load"))
        return attrs


class GloBirdLatestDayControlledLoadSensor(GloBirdServiceBaseSensor):
    """Latest day controlled-load usage."""

    sensor_key = "latest_day_controlled_load"
    sensor_name = "Latest Day Controlled Load"
    sensor_icon = "mdi:water-boiler"
    sensor_unit = UnitOfEnergy.KILO_WATT_HOUR
    sensor_device_class = SensorDeviceClass.ENERGY
    sensor_state_class = SensorStateClass.TOTAL

    @property
    def last_reset(self) -> datetime | None:
        """Return midnight of the latest controlled-load day."""
        summary = self._service_detail().get("usage_summary") or {}
        daily = summary.get("controlled_load_daily") or []
        latest = daily[-1] if daily and isinstance(daily[-1], dict) else {}
        return _day_reset_timestamp(latest.get("readDate"))

    @property
    def native_value(self) -> Any:
        """Return latest day controlled-load usage."""
        return (self._service_detail().get("usage_summary") or {}).get(
            "latest_day_controlled_load"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return latest day controlled-load attributes."""
        attrs = self._service_attrs()
        summary = self._service_detail().get("usage_summary") or {}
        attrs.update(usage_attributes(summary, direction="controlled_load"))
        return attrs


class GloBirdUsageRegisterSensor(GloBirdDailyStatisticsSensor):
    """Recent usage of one portal register, such as a time-of-use window.

    Created for energy registers that share their usage class with another
    register (see ``register_sensor`` in the usage summary). The entity is
    unavailable while the portal does not return its register.
    """

    sensor_key = "usage_register"
    sensor_name = "Usage Register"
    sensor_icon = "mdi:chart-timeline-variant"
    sensor_unit = UnitOfEnergy.KILO_WATT_HOUR
    sensor_device_class = SensorDeviceClass.ENERGY
    sensor_state_class = SensorStateClass.TOTAL

    def __init__(
        self,
        coordinator: GloBirdCoordinator,
        config_entry: ConfigEntry,
        service: dict[str, Any],
        register: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, service)
        self._slug = str(register.get("slug") or "unknown")
        self._attr_unique_id = _register_unique_id(
            config_entry, self._service_id, self._slug
        )
        label = " ".join(
            str(part).strip()
            for part in (register.get("suffix"), register.get("chargeType"))
            if part and str(part).strip()
        )
        self._attr_name = f"Recent {label or self._slug}"
        if register.get("direction") == "export":
            self._attr_icon = "mdi:solar-power"

    def _register(self) -> dict[str, Any] | None:
        """Return this sensor's register from the latest usage summary."""
        summary = self._service_detail().get("usage_summary") or {}
        for register in summary.get("registers") or []:
            if isinstance(register, dict) and register.get("slug") == self._slug:
                return register
        return None

    @property
    def available(self) -> bool:
        """Return whether the portal still returns this register."""
        return bool(super().available) and self._register() is not None

    async def _async_upload_statistics(self) -> None:
        """Upload this register's daily usage statistics."""
        register = self._register()
        if register is None:
            return
        await self._async_upload_daily_external_statistics(
            register.get("daily") or [],
            date_key="readDate",
            value_key="usage",
            unit_class=EnergyConverter.UNIT_CLASS,
        )

    @property
    def native_value(self) -> Any:
        """Return the register's recent usage total."""
        register = self._register()
        return register.get("total") if register else None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return register metadata, time-of-use windows and recent days."""
        attrs = self._service_attrs()
        register = self._register() or {}
        daily = register.get("daily")
        daily_rows = daily if isinstance(daily, list) else []
        attrs.update(
            {
                "register_key": register.get("key"),
                "suffix": register.get("suffix"),
                "chargeType": register.get("chargeType"),
                "chargeCategoryCode": register.get("chargeCategoryCode"),
                "direction": register.get("direction"),
                "usage_class": register.get("usage_class"),
                "time_periods": register.get("time_periods") or [],
                "latest_day": register.get("latest_day"),
                "latest_day_usage": register.get("latest_day_usage"),
                "daily": daily_rows[-ATTR_RECENT_ROW_LIMIT:],
                "daily_count": len(daily_rows),
            }
        )
        return attrs


class GloBirdCostTotalSensor(GloBirdDailyStatisticsSensor):
    """Recent cost total sensor (compatible with HA Energy Dashboard total cost tracking)."""

    sensor_key = "cost_total"
    sensor_name = "Recent Cost Total"
    sensor_icon = "mdi:cash-multiple"
    sensor_unit = CURRENCY_AUD
    sensor_device_class = SensorDeviceClass.MONETARY
    sensor_state_class = SensorStateClass.TOTAL

    async def _async_upload_statistics(self) -> None:
        """Upload daily cost statistics."""
        summary = self._service_detail().get("cost_summary") or {}
        await self._async_upload_daily_external_statistics(
            summary.get("daily_totals") or [],
            date_key="date",
            value_key="amount",
            unit_class=None,
        )

    @property
    def native_value(self) -> Any:
        """Return total recent cost."""
        detail = self._service_detail()
        val = (detail.get("cost_summary") or {}).get("total_amount")
        return val if val is not None else (0.0 if detail else None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return cost attributes."""
        attrs = self._service_attrs()
        summary = self._service_detail().get("cost_summary") or {}
        attrs.update(cost_attributes(summary))
        return attrs


class GloBirdLatestDayCostSensor(GloBirdServiceBaseSensor):
    """Latest daily cost sensor (compatible with HA Energy Dashboard total cost tracking)."""

    sensor_key = "latest_day_cost"
    sensor_name = "Latest Daily Cost"
    sensor_icon = "mdi:calendar-today"
    sensor_unit = CURRENCY_AUD
    sensor_device_class = SensorDeviceClass.MONETARY
    sensor_state_class = SensorStateClass.TOTAL

    @property
    def last_reset(self) -> datetime | None:
        """Return midnight of the latest complete cost day."""
        summary = self._service_detail().get("cost_summary") or {}
        return _day_reset_timestamp(summary.get("latest_day"))

    @property
    def native_value(self) -> Any:
        """Return latest day cost."""
        return (self._service_detail().get("cost_summary") or {}).get(
            "latest_day_amount"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return latest daily cost attributes."""
        attrs = self._service_attrs()
        summary = self._service_detail().get("cost_summary") or {}
        attrs.update(
            {
                "latest_day": summary.get("latest_day"),
                "latest_day_import_cost": summary.get("latest_day_import_cost"),
                "latest_day_export_credit": summary.get("latest_day_export_credit"),
                "latest_available_day": summary.get("latest_available_day"),
                "latest_available_day_complete": summary.get(
                    "latest_available_day_complete"
                ),
                "zerohero_credit": summary.get("latest_day_zerohero_credit"),
            }
        )
        return attrs


class GloBirdSolarExportCreditTotalSensor(GloBirdDailyStatisticsSensor):
    """Recent solar export compensation total sensor for the HA Energy Dashboard."""

    sensor_key = "solar_export_credit_total"
    sensor_name = "Recent Solar Export Credit Total"
    sensor_icon = "mdi:cash-plus"
    sensor_unit = CURRENCY_AUD
    sensor_device_class = SensorDeviceClass.MONETARY
    sensor_state_class = SensorStateClass.TOTAL

    async def _async_upload_statistics(self) -> None:
        """Upload daily solar export credit statistics."""
        summary = self._service_detail().get("cost_summary") or {}
        await self._async_upload_daily_external_statistics(
            summary.get("daily_export_credit_totals") or [],
            date_key="date",
            value_key="amount",
            unit_class=None,
        )

    @property
    def native_value(self) -> Any:
        """Return total recent solar export compensation in AUD."""
        detail = self._service_detail()
        val = (detail.get("cost_summary") or {}).get("total_export_credit")
        return val if val is not None else (0.0 if detail else None)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return solar export credit attributes."""
        attrs = self._service_attrs()
        summary = self._service_detail().get("cost_summary") or {}
        attrs["latest_day"] = summary.get("latest_day")
        attrs["latest_day_export_credit"] = summary.get("latest_day_export_credit")
        return attrs


class GloBirdLatestDaySolarExportCreditSensor(GloBirdServiceBaseSensor):
    """Latest daily solar export compensation sensor for the HA Energy Dashboard."""

    sensor_key = "latest_day_solar_export_credit"
    sensor_name = "Latest Daily Solar Export Credit"
    sensor_icon = "mdi:cash-refund"
    sensor_unit = CURRENCY_AUD
    sensor_device_class = SensorDeviceClass.MONETARY
    sensor_state_class = SensorStateClass.TOTAL

    @property
    def last_reset(self) -> datetime | None:
        """Return midnight of the latest complete cost day."""
        summary = self._service_detail().get("cost_summary") or {}
        return _day_reset_timestamp(summary.get("latest_day"))

    @property
    def native_value(self) -> Any:
        """Return latest day solar export compensation in AUD."""
        return (self._service_detail().get("cost_summary") or {}).get(
            "latest_day_export_credit"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return latest daily solar export credit attributes."""
        attrs = self._service_attrs()
        summary = self._service_detail().get("cost_summary") or {}
        attrs["latest_day"] = summary.get("latest_day")
        attrs["total_export_credit"] = summary.get("total_export_credit")
        return attrs


class GloBirdZeroHeroStatusSensor(GloBirdServiceBaseSensor):
    """Local-day ZEROHERO credit status."""

    sensor_key = "zerohero_status"
    sensor_name = "ZeroHero Status"
    sensor_icon = "mdi:check-decagram"
    sensor_device_class = SensorDeviceClass.ENUM
    _attr_options = ZEROHERO_STATUS_OPTIONS

    def __init__(
        self,
        coordinator: GloBirdCoordinator,
        config_entry: ConfigEntry,
        service: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, config_entry, service)
        self._zerohero_boundary_unsub: Callable[[], None] | None = None

    async def async_added_to_hass(self) -> None:
        """Schedule state refreshes at local ZEROHERO day boundaries."""
        await super().async_added_to_hass()
        self.async_on_remove(self._cancel_zerohero_boundary_update)
        self._schedule_zerohero_boundary_update()

    def _cancel_zerohero_boundary_update(self) -> None:
        """Cancel the pending ZEROHERO boundary update."""
        if self._zerohero_boundary_unsub is not None:
            self._zerohero_boundary_unsub()
            self._zerohero_boundary_unsub = None

    def _schedule_zerohero_boundary_update(self) -> None:
        """Schedule the next local time boundary update."""
        self._cancel_zerohero_boundary_update()
        self._zerohero_boundary_unsub = async_track_point_in_time(
            self.hass,
            self._handle_zerohero_boundary_update,
            _next_zerohero_status_boundary(dt_util.now()),
        )

    @callback
    def _handle_zerohero_boundary_update(self, _now: datetime) -> None:
        """Refresh the entity when the local day/window state changes."""
        self.async_write_ha_state()
        self._schedule_zerohero_boundary_update()

    @property
    def native_value(self) -> Any:
        """Return the latest complete ZEROHERO status."""
        summary = self._service_detail().get("cost_summary") or {}
        return _zerohero_status(summary)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return ZEROHERO detail attributes."""
        attrs = self._service_attrs()
        summary = self._service_detail().get("cost_summary") or {}
        now = dt_util.now()
        last_result, latest_day, latest_day_raw = _zerohero_last_result(summary)
        attrs.update(
            {
                "latest_day": summary.get("latest_day"),
                "zerohero_credit": summary.get("latest_day_zerohero_credit"),
                "latest_day_cost": summary.get("latest_day_amount"),
                "result_is_for_today": (
                    latest_day is not None and latest_day == now.date()
                ),
                "last_result": last_result,
                "last_result_day": latest_day_raw,
                "latest_available_day": summary.get("latest_available_day"),
                "latest_available_day_complete": summary.get(
                    "latest_available_day_complete"
                ),
            }
        )
        return attrs


class GloBirdExpectedMonthlyCostSensor(GloBirdServiceBaseSensor):
    """Projected cost for the current billing period."""

    sensor_key = "expected_month_cost"
    sensor_name = "Expected Monthly Cost"
    sensor_icon = "mdi:cash-clock"
    sensor_unit = CURRENCY_AUD
    sensor_device_class = SensorDeviceClass.MONETARY
    sensor_state_class = None

    @property
    def native_value(self) -> Any:
        """Return projected billing-period cost."""
        cost_summary = self._service_detail().get("cost_summary") or {}
        projected = build_billing_period_projection(
            cost_summary.get("daily_totals"),
            _billing_period_start(self.coordinator.data or {}),
        )
        return projected.get("projected_cost")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return projected billing-period cost calculation inputs."""
        attrs = self._service_attrs()
        cost_summary = self._service_detail().get("cost_summary") or {}
        projected = build_billing_period_projection(
            cost_summary.get("daily_totals"),
            _billing_period_start(self.coordinator.data or {}),
        )
        attrs.update(projected)
        attrs["calculation"] = (
            "billing_period_cost_to_date / completed_days * period_days"
        )
        return attrs


def _billing_period_start(data: dict[str, Any]) -> date | None:
    """Return the start date of the current billing period (latest invoice issue date)."""
    dashboard = _payload_data(data.get("dashboard")) or {}
    invoice = dashboard.get("lastestInvoice") or {}
    issued = invoice.get("issuedDate")
    if not issued:
        return None
    try:
        return date.fromisoformat(str(issued).split("T")[0])
    except ValueError:
        return None


class GloBirdBillingPeriodDaysSensor(GloBirdServiceBaseSensor):
    """Number of days elapsed in the current billing period."""

    sensor_key = "billing_period_days"
    sensor_name = "Billing Period Days"
    sensor_icon = "mdi:calendar-range"

    @property
    def native_value(self) -> Any:
        """Return days of completed data since billing period start.

        Excludes today because GloBird's usage/cost data only covers
        through end of yesterday — keeps this sensor consistent with
        Billing Period Cost and the daily usage/cost sensors.
        """
        start = _billing_period_start(self.coordinator.data or {})
        if start is None:
            return None
        return _billing_period_completed_days(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return billing period attributes."""
        attrs = self._service_attrs()
        start = _billing_period_start(self.coordinator.data or {})
        attrs["billing_period_start"] = start.isoformat() if start else None
        return attrs


class GloBirdBillingPeriodCostSensor(GloBirdServiceBaseSensor):
    """Cost so far in the current billing period (compatible with HA Energy Dashboard)."""

    sensor_key = "billing_period_cost"
    sensor_name = "Billing Period Cost"
    sensor_icon = "mdi:cash-clock"
    sensor_unit = CURRENCY_AUD
    sensor_device_class = SensorDeviceClass.MONETARY
    sensor_state_class = SensorStateClass.TOTAL

    @property
    def last_reset(self) -> datetime | None:
        """Return midnight on the billing period start date."""
        start = _billing_period_start(self.coordinator.data or {})
        if start is None:
            return None
        tzinfo = dt_util.now().tzinfo or UTC
        return datetime.combine(start, dt_time.min, tzinfo=tzinfo)

    @property
    def native_value(self) -> Any:
        """Return net cost since billing period start."""
        detail = self._service_detail()
        start = _billing_period_start(self.coordinator.data or {})
        cost_summary = detail.get("cost_summary") or {}
        daily_totals = cost_summary.get("daily_totals", [])
        if not daily_totals:
            return 0.0 if detail else None
        if start is None:
            return cost_summary.get("total_amount")
        start_slash = start.strftime("%Y/%m/%d")
        total = sum(
            (row.get("amount") or 0.0)
            for row in daily_totals
            if str(row.get("date") or "") >= start_slash
        )
        return round(total, 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return billing period cost attributes."""
        attrs = self._service_attrs()
        start = _billing_period_start(self.coordinator.data or {})
        attrs["billing_period_start"] = start.isoformat() if start else None
        return attrs


class GloBirdWeatherSummarySensor(GloBirdServiceBaseSensor):
    """Weather summary sensor."""

    sensor_key = "weather_summary"
    sensor_name = "Weather Summary"
    sensor_icon = "mdi:weather-partly-cloudy"
    sensor_unit = UnitOfTemperature.CELSIUS
    sensor_device_class = SensorDeviceClass.TEMPERATURE
    sensor_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> Any:
        """Return latest max temperature."""
        return (self._service_detail().get("weather_summary") or {}).get(
            "latest_max_temp"
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return weather attributes."""
        attrs = self._service_attrs()
        summary = self._service_detail().get("weather_summary") or {}
        attrs.update(
            {
                "days": summary.get("days"),
                "latest_date": summary.get("latest_date"),
                "latest_min_temp": summary.get("latest_min_temp"),
                "latest_max_temp": summary.get("latest_max_temp"),
                "daily": summary.get("daily", []),
            }
        )
        return attrs
