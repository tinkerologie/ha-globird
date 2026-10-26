"""Tests for GloBird sensor helpers."""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

COMPONENT_PATH = Path(__file__).parents[1] / "custom_components"
INTEGRATION_PATH = COMPONENT_PATH / "globird"
GAS_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "globird_gas_responses.json"

custom_components = types.ModuleType("custom_components")
custom_components.__path__ = [str(COMPONENT_PATH)]  # type: ignore[attr-defined]
globird_package = types.ModuleType("custom_components.globird")
globird_package.__path__ = [str(INTEGRATION_PATH)]  # type: ignore[attr-defined]
sys.modules["custom_components"] = custom_components
sys.modules["custom_components.globird"] = globird_package

homeassistant = types.ModuleType("homeassistant")
components = types.ModuleType("homeassistant.components")
sensor_component = types.ModuleType("homeassistant.components.sensor")
config_entries = types.ModuleType("homeassistant.config_entries")
const = types.ModuleType("homeassistant.const")
core = types.ModuleType("homeassistant.core")
recorder = types.ModuleType("homeassistant.components.recorder")
recorder_models = types.ModuleType("homeassistant.components.recorder.models")
helpers = types.ModuleType("homeassistant.helpers")
entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
event = types.ModuleType("homeassistant.helpers.event")
start = types.ModuleType("homeassistant.helpers.start")
storage = types.ModuleType("homeassistant.helpers.storage")
update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
util = types.ModuleType("homeassistant.util")
dt = types.ModuleType("homeassistant.util.dt")
util_logging = types.ModuleType("homeassistant.util.logging")
unit_conversion = types.ModuleType("homeassistant.util.unit_conversion")


class SensorDeviceClass:
    """Minimal sensor device classes used by the integration."""

    ENERGY = "energy"
    ENUM = "enum"
    GAS = "gas"
    MONETARY = "monetary"
    TEMPERATURE = "temperature"
    TIMESTAMP = "timestamp"


class SensorEntity:
    """Minimal stand-in for Home Assistant's SensorEntity."""

    @property
    def unique_id(self) -> str | None:
        return getattr(self, "_attr_unique_id", None)


class SensorStateClass:
    """Minimal sensor state classes used by the integration."""

    MEASUREMENT = "measurement"
    TOTAL = "total"
    TOTAL_INCREASING = "total_increasing"


class CoordinatorEntity:
    """Minimal stand-in for Home Assistant's CoordinatorEntity."""

    def __class_getitem__(cls, _item: Any) -> type[CoordinatorEntity]:
        return cls

    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator
        self.hass = object()
        self.entity_id: str | None = None
        self._remove_callbacks: list[Any] = []
        self._write_count = 0

    async def async_added_to_hass(self) -> None:
        return None

    def async_on_remove(self, callback: Any) -> None:
        self._remove_callbacks.append(callback)

    def async_write_ha_state(self) -> None:
        self._write_count += 1

    def _handle_coordinator_update(self) -> None:
        return None

    @property
    def available(self) -> bool:
        return bool(getattr(self.coordinator, "last_update_success", True))


class DataUpdateCoordinator:
    """Minimal stand-in for Home Assistant's DataUpdateCoordinator."""

    def __class_getitem__(cls, _item: Any) -> type[DataUpdateCoordinator]:
        return cls

    def __init__(
        self,
        *_args: Any,
        update_interval: timedelta | None = None,
        **_kwargs: Any,
    ) -> None:
        self.update_interval = update_interval


class Store:
    """Minimal stand-in for Home Assistant storage."""

    def __class_getitem__(cls, _item: Any) -> type[Store]:
        return cls

    def __init__(self, *_args: Any, **_kwargs: Any) -> None:
        return None


class UpdateFailed(Exception):
    """Minimal stand-in for Home Assistant's update failure."""


class StatisticMeanType:
    """Minimal recorder mean type enum stub."""

    NONE = 0


def async_track_point_in_time(*_args: Any, **_kwargs: Any) -> Any:
    """Return an unsubscribe callback."""
    return lambda: None


def async_at_started(hass: Any, at_start_cb: Any) -> Any:
    """Run the callback now, as Home Assistant does once it has started."""
    at_start_cb(hass)
    return lambda: None


sensor_component.SensorDeviceClass = SensorDeviceClass
sensor_component.SensorEntity = SensorEntity
sensor_component.SensorStateClass = SensorStateClass
config_entries.ConfigEntry = object
const.EntityCategory = types.SimpleNamespace(DIAGNOSTIC="diagnostic")
const.UnitOfEnergy = types.SimpleNamespace(KILO_WATT_HOUR="kWh")
const.UnitOfTemperature = types.SimpleNamespace(CELSIUS="C")
const.UnitOfVolume = types.SimpleNamespace(CUBIC_METERS="m3")
core.HomeAssistant = object
core.callback = lambda func: func
entity_platform.AddEntitiesCallback = object
event.async_track_point_in_time = async_track_point_in_time
start.async_at_started = async_at_started
storage.Store = Store
update_coordinator.CoordinatorEntity = CoordinatorEntity
update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
update_coordinator.UpdateFailed = UpdateFailed
recorder_models.StatisticMeanType = StatisticMeanType
recorder_models.StatisticData = lambda **kwargs: dict(kwargs)
recorder_models.StatisticMetaData = lambda **kwargs: dict(kwargs)
unit_conversion.VolumeConverter = types.SimpleNamespace(UNIT_CLASS="volume")
unit_conversion.EnergyConverter = types.SimpleNamespace(UNIT_CLASS="energy")
dt.now = lambda: datetime.now(UTC)
util.dt = dt
util_logging.log_exception = lambda *_args, **_kwargs: None
util.logging = util_logging
util.unit_conversion = unit_conversion

components.sensor = sensor_component
components.recorder = recorder
helpers.entity_platform = entity_platform
helpers.event = event
helpers.start = start
helpers.storage = storage
helpers.update_coordinator = update_coordinator
homeassistant.components = components
homeassistant.config_entries = config_entries
homeassistant.const = const
homeassistant.core = core
homeassistant.helpers = helpers
homeassistant.util = util

sys.modules["homeassistant"] = homeassistant
sys.modules["homeassistant.components"] = components
sys.modules["homeassistant.components.recorder"] = recorder
sys.modules["homeassistant.components.recorder.models"] = recorder_models
sys.modules["homeassistant.components.sensor"] = sensor_component
sys.modules["homeassistant.config_entries"] = config_entries
sys.modules["homeassistant.const"] = const
sys.modules["homeassistant.core"] = core
sys.modules["homeassistant.helpers"] = helpers
sys.modules["homeassistant.helpers.entity_platform"] = entity_platform
sys.modules["homeassistant.helpers.event"] = event
sys.modules["homeassistant.helpers.start"] = start
sys.modules["homeassistant.helpers.storage"] = storage
sys.modules["homeassistant.helpers.update_coordinator"] = update_coordinator
sys.modules["homeassistant.util"] = util
sys.modules["homeassistant.util.dt"] = dt
sys.modules["homeassistant.util.logging"] = util_logging
sys.modules["homeassistant.util.unit_conversion"] = unit_conversion

sensor = importlib.import_module("custom_components.globird.sensor")
client_module = importlib.import_module("custom_components.globird.client")
ZEROHERO_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "globird_zerohero_tou_responses.json"
)


class FakeEntry:
    """Config entry stand-in that records unload callbacks."""

    def __init__(self, entry_id: str = "entry-1", runtime_data: Any = None) -> None:
        self.entry_id = entry_id
        self.runtime_data = runtime_data
        self.unload_callbacks: list[Any] = []
        self.background_tasks: list[tuple[Any, str]] = []

    def async_on_unload(self, func: Any) -> None:
        self.unload_callbacks.append(func)

    def async_create_background_task(self, _hass: Any, target: Any, name: str) -> None:
        self.background_tasks.append((target, name))


class ListenerMixin:
    """Coordinator stand-in support for ``async_add_listener``."""

    listeners: list[Any]

    def async_add_listener(self, listener: Any) -> Any:
        if not hasattr(self, "listeners"):
            self.listeners = []
        self.listeners.append(listener)
        return lambda: self.listeners.remove(listener)


def load_gas_fixtures() -> dict[str, Any]:
    """Load dedicated gas fixture payloads."""
    return json.loads(GAS_FIXTURE_PATH.read_text())


def test_expected_monthly_cost_uses_existing_mdi_icon() -> None:
    """Expected Monthly Cost should not point at a non-existent MDI icon."""
    assert sensor.GloBirdExpectedMonthlyCostSensor.sensor_icon == "mdi:cash-clock"


def test_billing_period_days_uses_home_assistant_local_date(monkeypatch: Any) -> None:
    """Billing Period Days should follow the configured HA timezone."""
    data = {
        "dashboard": {
            "data": {
                "lastestInvoice": {
                    "issuedDate": "2026-07-02T00:00:00",
                },
            },
        },
    }
    local_tz = timezone(timedelta(hours=10))
    monkeypatch.setattr(
        sensor.dt_util,
        "now",
        lambda: datetime(2026, 7, 2, 0, 30, tzinfo=local_tz),
    )

    assert sensor._billing_period_completed_days(data) == 0

    monkeypatch.setattr(
        sensor.dt_util,
        "now",
        lambda: datetime(2026, 7, 3, 0, 30, tzinfo=local_tz),
    )

    assert sensor._billing_period_completed_days(data) == 1


def test_zerohero_status_reports_latest_complete_result() -> None:
    """Achieved/missed should follow the latest complete portal result."""
    local_tz = timezone(timedelta(hours=10))
    yesterday_summary = {
        "latest_day": "2026/07/01",
        "latest_day_zerohero_credit": 0.0,
        "latest_day_zerohero_achieved": False,
    }

    assert (
        sensor._zerohero_status(
            yesterday_summary,
            datetime(2026, 7, 2, 20, 59, tzinfo=local_tz),
        )
        == "missed"
    )
    assert (
        sensor._zerohero_status(
            yesterday_summary,
            datetime(2026, 7, 2, 21, 0, tzinfo=local_tz),
        )
        == "missed"
    )

    today_summary = {
        "latest_day": "2026/07/02",
        "latest_day_zerohero_credit": 0.0,
        "latest_day_zerohero_achieved": False,
    }

    assert (
        sensor._zerohero_status(
            today_summary,
            datetime(2026, 7, 2, 21, 30, tzinfo=local_tz),
        )
        == "missed"
    )

    today_summary["latest_day_zerohero_credit"] = -0.3
    today_summary["latest_day_zerohero_achieved"] = True

    assert (
        sensor._zerohero_status(
            today_summary,
            datetime(2026, 7, 2, 21, 30, tzinfo=local_tz),
        )
        == "achieved"
    )


def test_zerohero_status_is_unknown_without_usable_cost_summary() -> None:
    """Missing latest complete cost data should remain unknown."""
    assert sensor._zerohero_status({}) == "unknown"


def test_is_gas_service_matches_service_type() -> None:
    """Gas services should be detected from serviceType."""
    assert sensor._is_gas_service({"serviceType": "Gas"}) is True
    assert sensor._is_gas_service({"serviceType": "POWER"}) is False


def test_non_gas_service_sensor_name_uses_original_title() -> None:
    """Non-gas service sensors should keep the original title-only naming."""

    class FakeCoordinator:
        data = {}

    entity = sensor.GloBirdBillingPeriodCostSensor(
        FakeCoordinator(),
        types.SimpleNamespace(entry_id="entry-1"),
        {
            "accountServiceId": 810965,
            "serviceType": "Power",
            "siteIdentifier": "NMI00000001",
        },
    )

    assert entity._attr_name == "Billing Period Cost"


def test_gas_service_sensor_name_includes_site_suffix() -> None:
    """Gas service sensors should include identifiers to avoid ambiguous names."""

    class FakeCoordinator:
        data = {
            "service_data": {
                "123456": {
                    "service": {
                        "accountServiceId": 123456,
                        "siteIdentifier": "55104217567",
                        "serviceType": "Gas",
                    },
                    "gas_reading_summary": {},
                }
            }
        }

    reading = sensor.GloBirdLatestGasReadingSensor(
        FakeCoordinator(),
        types.SimpleNamespace(entry_id="entry-1"),
        {
            "accountServiceId": 123456,
            "serviceType": "Gas",
            "siteIdentifier": "55104217567",
        },
    )
    reading_date = sensor.GloBirdLatestGasReadingDateSensor(
        FakeCoordinator(),
        types.SimpleNamespace(entry_id="entry-1"),
        {
            "accountServiceId": 123456,
            "serviceType": "Gas",
            "siteIdentifier": "55104217567",
        },
    )

    assert reading._attr_name == "Latest Gas Reading (55104217567)"
    assert reading_date._attr_name == "Latest Gas Reading Date (55104217567)"


def test_gas_shared_service_sensors_include_site_suffix() -> None:
    """Shared service sensors should also include suffixes when the service is gas."""

    class FakeCoordinator:
        data = {
            "service_data": {
                "123456": {
                    "service": {
                        "accountServiceId": 123456,
                        "siteIdentifier": "55104217567",
                        "serviceType": "Gas",
                    }
                }
            }
        }

    status = sensor.GloBirdServiceStatusSensor(
        FakeCoordinator(),
        types.SimpleNamespace(entry_id="entry-1"),
        {
            "accountServiceId": 123456,
            "serviceType": "Gas",
            "siteIdentifier": "55104217567",
        },
    )
    meter = sensor.GloBirdMeterInfoSensor(
        FakeCoordinator(),
        types.SimpleNamespace(entry_id="entry-1"),
        {
            "accountServiceId": 123456,
            "serviceType": "Gas",
            "siteIdentifier": "55104217567",
        },
    )

    assert status._attr_name == "Service Status (55104217567)"
    assert meter._attr_name == "Meter Info (55104217567)"


def test_safe_statistic_id_sanitizes_for_recorder() -> None:
    """Recorder statistic IDs must contain only supported characters."""
    assert (
        sensor._safe_statistic_id(
            "01ABC-service 123/latest-gas-reading",
            fallback="service-1",
        )
        == "svc_01abc_service_123_latest_gas_reading"
    )
    assert sensor._safe_statistic_id("a---b___c", fallback="x") == "a_b_c"


def test_statistic_id_uses_recorder_domain_prefix() -> None:
    """Statistic IDs should use recorder's <domain>:<slug> format."""
    suffix = sensor._safe_statistic_id("entry-1_service_123_latest_gas_reading", "x")
    statistic_id = f"{sensor.DOMAIN}:{suffix}"
    assert statistic_id.startswith(f"{sensor.DOMAIN}:")
    assert "__" not in statistic_id


def test_gas_statistics_continue_across_meter_replacement() -> None:
    """A lower replacement-meter index should continue the cumulative sum."""
    local_tz = timezone(timedelta(hours=10))
    statistics = sensor._build_gas_statistics(
        [
            {"date": "2026-01-01", "read_index": 100.0, "serial": "old"},
            {"date": "2026-02-01", "read_index": 110.0, "serial": "old"},
            {"date": "2026-03-01", "read_index": 5.0, "serial": "new"},
            {"date": "2026-04-01", "read_index": 12.0, "serial": "new"},
        ],
        tzinfo=local_tz,
    )

    assert [row["state"] for row in statistics] == [100.0, 110.0, 5.0, 12.0]
    assert [row["sum"] for row in statistics] == [0.0, 10.0, 10.0, 17.0]
    assert statistics[0]["start"].utcoffset() == timedelta(hours=10)


def test_gas_statistics_ignore_downward_correction_without_double_counting() -> None:
    """A corrected lower read must not be counted again when the index recovers."""
    statistics = sensor._build_gas_statistics(
        [
            {"date": "2026-01-01", "read_index": 100.0, "serial": "meter"},
            {"date": "2026-02-01", "read_index": 95.0, "serial": "meter"},
            {"date": "2026-03-01", "read_index": 102.0, "serial": "meter"},
        ],
        tzinfo=UTC,
    )

    assert [row["sum"] for row in statistics] == [0.0, 0.0, 2.0]


def test_gas_statistics_first_read_starts_sum_at_zero() -> None:
    """The first meter index is a baseline, not consumption.

    Home Assistant's recorder computes change for the first-ever statistics
    row as ``sum - 0``, so a first sum equal to the meter index would show the
    whole index as consumed in the Energy dashboard.
    """
    statistics = sensor._build_gas_statistics(
        [
            {"date": "2026-01-01", "read_index": 746.0, "serial": "meter"},
            {"date": "2026-04-01", "read_index": 790.5, "serial": "meter"},
        ],
        tzinfo=UTC,
    )

    assert [row["state"] for row in statistics] == [746.0, 790.5]
    assert [row["sum"] for row in statistics] == [0.0, 44.5]


def test_gas_statistics_single_read_has_zero_sum() -> None:
    """A single published read yields a zero sum with the index as state."""
    statistics = sensor._build_gas_statistics(
        [{"date": "2026-01-01", "read_index": 790.0, "serial": "meter"}],
        tzinfo=UTC,
    )

    assert len(statistics) == 1
    assert statistics[0]["state"] == 790.0
    assert statistics[0]["sum"] == 0.0


def test_gas_statistics_new_serial_first_read_is_baseline() -> None:
    """A replacement meter's first read is its baseline and adds no usage."""
    statistics = sensor._build_gas_statistics(
        [
            {"date": "2026-01-01", "read_index": 500.0, "serial": "old"},
            {"date": "2026-02-01", "read_index": 520.0, "serial": "old"},
            {"date": "2026-03-01", "read_index": 900.0, "serial": "new"},
            {"date": "2026-04-01", "read_index": 930.0, "serial": "new"},
        ],
        tzinfo=UTC,
    )

    assert [row["sum"] for row in statistics] == [0.0, 20.0, 20.0, 50.0]


def test_gas_statistics_continue_from_stored_row_before_window() -> None:
    """Reads that left the portal window must not reset the sum to 0."""
    statistics = sensor._build_gas_statistics(
        [
            {"date": "2026-04-01", "read_index": 790.0, "serial": "meter"},
            {"date": "2026-07-01", "read_index": 830.0, "serial": "meter"},
        ],
        tzinfo=UTC,
        stored_before=(746.0, 0.0),
    )

    assert [row["state"] for row in statistics] == [790.0, 830.0]
    assert [row["sum"] for row in statistics] == [44.0, 84.0]


def test_gas_statistics_stored_row_with_higher_index_adds_no_usage() -> None:
    """A first read below the stored index keeps the stored sum."""
    statistics = sensor._build_gas_statistics(
        [
            {"date": "2026-04-01", "read_index": 10.0, "serial": "new"},
            {"date": "2026-07-01", "read_index": 25.0, "serial": "new"},
        ],
        tzinfo=UTC,
        stored_before=(900.0, 50.0),
    )

    assert [row["sum"] for row in statistics] == [50.0, 65.0]


def test_daily_cumulative_statistics_first_row_is_first_day_usage() -> None:
    """Daily rows are per-day usage, so the first sum is that day's usage."""
    statistics = sensor._build_daily_cumulative_statistics(
        [
            {"readDate": "2026-09-26", "usage": 3.5},
            {"readDate": "2026-09-27", "usage": 4.25},
        ],
        date_key="readDate",
        value_key="usage",
        tzinfo=UTC,
    )

    assert [row["state"] for row in statistics] == [3.5, 4.25]
    assert [row["sum"] for row in statistics] == [3.5, 7.75]


def _gas_reading_entity(summary: dict[str, Any]) -> Any:
    """Return a Latest Gas Reading entity backed by the given summary."""

    class FakeCoordinator:
        data = {
            "service_data": {
                "123": {
                    "service": {"accountServiceId": 123, "serviceType": "Gas"},
                    "gas_reading_summary": summary,
                }
            }
        }

    return sensor.GloBirdLatestGasReadingSensor(
        FakeCoordinator(),
        types.SimpleNamespace(entry_id="entry-1"),
        {"accountServiceId": 123, "serviceType": "Gas"},
    )


def test_latest_gas_reading_is_unknown_without_reads() -> None:
    """A gas service with no published reads must report unknown, not 0.0."""
    assert _gas_reading_entity({}).native_value is None
    assert _gas_reading_entity({"latest_reading": None}).native_value is None


def test_latest_gas_reading_keeps_real_zero_reading() -> None:
    """A real 0.0 meter index is a reading, not a missing value."""
    assert _gas_reading_entity({"latest_reading": 0.0}).native_value == 0.0


def _install_recorder_stubs(
    monkeypatch: Any,
    stored_rows: list[dict[str, Any]] | Exception,
) -> tuple[list[tuple[Any, Any]], list[tuple[Any, ...]]]:
    """Stub the recorder APIs the statistics imports use."""
    uploaded: list[tuple[Any, Any]] = []
    queries: list[tuple[Any, ...]] = []

    async def add_statistics(_hass: Any, meta: Any, stats: Any) -> None:
        uploaded.append((meta, stats))

    def statistics_during_period(*args: Any) -> dict[str, list[dict[str, Any]]]:
        queries.append(args)
        if isinstance(stored_rows, Exception):
            raise stored_rows
        return {args[3].copy().pop(): stored_rows}

    class FakeRecorder:
        async def async_add_executor_job(self, func: Any, *args: Any) -> Any:
            return func(*args)

        def async_get_commit_future(self) -> Any:
            return None

    statistics_module = types.ModuleType("homeassistant.components.recorder.statistics")
    statistics_module.async_add_external_statistics = add_statistics
    statistics_module.statistics_during_period = statistics_during_period
    helpers_recorder = types.ModuleType("homeassistant.helpers.recorder")
    helpers_recorder.get_instance = lambda _hass: FakeRecorder()
    monkeypatch.setitem(
        sys.modules,
        "homeassistant.components.recorder.statistics",
        statistics_module,
    )
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.recorder", helpers_recorder)
    return uploaded, queries


_GAS_HISTORY = {
    "latest_reading": 790.0,
    "history": [
        {"date": "2026-01-01", "read_index": 746.0, "serial": "meter"},
        {"date": "2026-04-01", "read_index": 790.0, "serial": "meter"},
    ],
}


def test_gas_upload_first_import_starts_sum_at_zero(monkeypatch: Any) -> None:
    """First import: the uploaded sum starts at 0 with the index as state."""
    uploaded, queries = _install_recorder_stubs(monkeypatch, [])
    entity = _gas_reading_entity(_GAS_HISTORY)

    asyncio.run(entity._async_upload_historical_statistics())

    assert len(uploaded) == 1
    metadata, rows = uploaded[0]
    assert metadata["has_sum"] is True
    assert (
        metadata["statistic_id"]
        == f"{sensor.DOMAIN}:entry_1_service_123_latest_gas_reading"
    )
    assert metadata["unit_of_measurement"] == sensor.UnitOfVolume.CUBIC_METERS
    assert [row["state"] for row in rows] == [746.0, 790.0]
    assert [row["sum"] for row in rows] == [0.0, 44.0]
    assert queries[0][3] == {metadata["statistic_id"]}
    assert queries[0][2] == rows[0]["start"]
    assert queries[0][6] == {"state", "sum"}


def test_gas_upload_continues_from_stored_row(monkeypatch: Any) -> None:
    """A stored row before the window anchors the uploaded sums."""
    uploaded, _queries = _install_recorder_stubs(
        monkeypatch,
        [
            {"start": 1.0, "state": 600.0, "sum": 0.0},
            {"start": 2.0, "state": 700.0, "sum": 100.0},
        ],
    )
    entity = _gas_reading_entity(_GAS_HISTORY)

    asyncio.run(entity._async_upload_historical_statistics())

    assert [row["sum"] for row in uploaded[0][1]] == [146.0, 190.0]


def test_rebase_legacy_gas_rows_removes_initial_index() -> None:
    """Rows stored with the old index-based sum are rebased to start at 0."""
    start = datetime(2025, 10, 1, tzinfo=UTC)
    rebased = sensor._rebase_legacy_gas_rows(
        [
            {"start": start, "state": 700.0, "sum": 700.0},
            {"start": start + timedelta(days=60), "state": 730.0, "sum": 730.0},
        ]
    )

    assert [row["start"] for row in rebased] == [start, start + timedelta(days=60)]
    assert [row["state"] for row in rebased] == [700.0, 730.0]
    assert [row["sum"] for row in rebased] == [0.0, 30.0]


def test_rebase_legacy_gas_rows_leaves_current_rows_alone() -> None:
    """Rows without a legacy offset, or no rows, need no rebase."""
    start = datetime(2025, 10, 1, tzinfo=UTC)
    assert sensor._rebase_legacy_gas_rows([]) == []
    assert (
        sensor._rebase_legacy_gas_rows([{"start": start, "state": 700.0, "sum": 0.0}])
        == []
    )
    assert (
        sensor._rebase_legacy_gas_rows([{"start": start, "state": 0.0, "sum": 0.0}])
        == []
    )


def test_gas_upload_rebases_legacy_rows_outside_window(monkeypatch: Any) -> None:
    """Legacy rows outside the window are rewritten once without the index."""
    first = datetime(2025, 10, 1, tzinfo=UTC)
    second = datetime(2025, 12, 1, tzinfo=UTC)
    uploaded, _queries = _install_recorder_stubs(
        monkeypatch,
        [
            {"start": first.timestamp(), "state": 700.0, "sum": 700.0},
            {"start": second.timestamp(), "state": 730.0, "sum": 730.0},
        ],
    )
    entity = _gas_reading_entity(_GAS_HISTORY)

    asyncio.run(entity._async_upload_historical_statistics())

    rows = uploaded[0][1]
    assert rows[0]["start"] == first
    assert rows[1]["start"] == second
    assert [row["state"] for row in rows] == [700.0, 730.0, 746.0, 790.0]
    assert [row["sum"] for row in rows] == [0.0, 30.0, 46.0, 90.0]


def test_gas_upload_ignores_stored_rows_without_state_or_sum(
    monkeypatch: Any,
) -> None:
    """A stored row without a state or a sum cannot anchor the import."""
    for stored_row in (
        {"start": 1.0, "state": 700.0, "sum": None},
        {"start": 1.0, "state": None, "sum": 100.0},
    ):
        uploaded, _queries = _install_recorder_stubs(monkeypatch, [stored_row])
        entity = _gas_reading_entity(_GAS_HISTORY)

        asyncio.run(entity._async_upload_historical_statistics())

        assert len(uploaded) == 1
        assert [row["sum"] for row in uploaded[0][1]] == [0.0, 44.0]


def test_gas_upload_skipped_when_stored_rows_unreadable(monkeypatch: Any) -> None:
    """Rows are never rewritten when the stored anchor cannot be read."""
    uploaded, _queries = _install_recorder_stubs(
        monkeypatch, RuntimeError("database locked")
    )
    entity = _gas_reading_entity(_GAS_HISTORY)

    asyncio.run(entity._async_upload_historical_statistics())

    assert uploaded == []


def test_latest_gas_reading_has_no_state_class() -> None:
    """The meter index entity must not compile its own long-term statistics.

    The imported ``globird:`` external statistic is the Energy dashboard
    source; a recorder-compiled sum on a quarterly index books each read
    jump into a single hour.
    """
    entity = _gas_reading_entity({"latest_reading": 790.0})

    assert entity._attr_state_class is None
    assert entity._attr_device_class == sensor.SensorDeviceClass.GAS
    assert entity._attr_native_unit_of_measurement == sensor.UnitOfVolume.CUBIC_METERS
    assert entity.native_value == 790.0


def test_latest_gas_reading_sensor_exposes_reading_summary() -> None:
    """Latest Gas Reading sensor should surface parsed basic meter data."""
    gas_fixture = load_gas_fixtures()["gas_service_data"]

    class FakeCoordinator:
        data = {
            "service_data": {
                "123456": gas_fixture,
            }
        }

    sensor_entity = sensor.GloBirdLatestGasReadingSensor(
        FakeCoordinator(),
        types.SimpleNamespace(entry_id="entry-1"),
        {"accountServiceId": 123456, "serviceType": "Gas"},
    )

    assert sensor_entity.native_value == 3050.0
    assert sensor_entity.extra_state_attributes["latest_reading_date"] == "2026-07-12"
    assert sensor_entity.extra_state_attributes["history_count"] == 1


def test_global_sensors_return_values_and_attributes() -> None:
    """Global sensor descriptors should map coordinator data into state values."""

    class FakeCoordinator:
        data = {
            "dashboard": {
                "data": {
                    "currentBalance": 42.2,
                    "accountId": 1,
                    "accountNumber": "A1",
                    "lastestCorrespondence": {"id": 1},
                    "lastestInvoice": {"amount": 12.34},
                    "recentAccountTransactions": [{"id": "t1"}],
                }
            },
            "balance": {
                "data": {
                    "balance": 55.0,
                    "maxRefundableAmount": 10.0,
                    "showRefundableAmount": True,
                }
            },
            "signup_info": {"data": [1, 2, 3]},
            "last_update": 1700000000,
            "_fetch_errors": {},
        }

    entities = [
        sensor.GloBirdGlobalSensor(
            FakeCoordinator(),
            types.SimpleNamespace(entry_id="entry-1"),
            description,
        )
        for description in sensor.GLOBAL_SENSORS
    ]

    assert len(entities) == len(sensor.GLOBAL_SENSORS)
    values = {entity._description.key: entity.native_value for entity in entities}
    assert values["balance"] == -55.0
    assert values["dashboard_balance"] == -42.2
    assert values["latest_invoice"] == 12.34
    assert values["signup_services"] == 3
    assert values["refresh_status"] == "ok"

    attrs = {
        entity._description.key: entity.extra_state_attributes for entity in entities
    }
    assert attrs["balance"]["max_refundable_amount"] == 10.0
    assert attrs["dashboard_balance"]["account_number"] == "A1"


def test_service_sensors_return_expected_values() -> None:
    """Service-level sensors should read from service_data generated by API summaries."""

    service = {
        "accountServiceId": 810965,
        "siteIdentifier": "NMI-1",
        "siteAddress": "Street",
        "postCode": "3000",
        "serviceType": "Power",
        "accountId": 1,
        "accountNumber": "A1",
    }
    detail = {
        "service": service,
        "status": {"status": "Switched"},
        "meter": {"meterReadType": "SMART", "serialStatus": "Active"},
        "usage_summary": {
            "total_usage": 10.5,
            "latest_day_usage": 1.2,
            "total_export": 3.4,
            "latest_day_export": 0.3,
            "daily": [{"readDate": "2026-07-01", "usage": 1.2}],
            "export_daily": [{"readDate": "2026-07-01", "usage": 0.3}],
            "latest_intervals": [0.4, 0.8],
            "registers": [],
        },
        "cost_summary": {
            "total_amount": 12.5,
            "latest_day_amount": 1.1,
            "latest_day": "2026/07/01",
            "latest_available_day": "2026/07/01",
            "latest_available_day_complete": True,
            "latest_day_zerohero_credit": -0.2,
            "latest_day_zerohero_achieved": True,
            "daily": [],
            "daily_totals": [{"date": "2026/07/01", "amount": 1.1}],
            "available_daily": [],
            "categories": [],
        },
        "latest_data_status": {
            "status": "ready",
            "latest_ready_day": "2026/07/01",
            "latest_usage_day": "2026/07/01",
            "latest_cost_day": "2026/07/01",
            "latest_available_cost_day": "2026/07/01",
            "latest_available_cost_day_complete": True,
            "incomplete_cost_days": [],
        },
        "weather_summary": {
            "days": 1,
            "latest_date": "2026-07-01",
            "latest_min_temp": 12,
            "latest_max_temp": 27,
            "daily": [{"dateAsDate": "2026-07-01", "obMinTemp": 12, "obMaxTemp": 27}],
        },
    }

    class FakeCoordinator:
        data = {
            "service_data": {"810965": detail},
            "dashboard": {
                "data": {"lastestInvoice": {"issuedDate": "2026-07-01T00:00:00"}}
            },
            "last_update": 1700000000,
        }

    entry = types.SimpleNamespace(entry_id="entry-1")
    created = [
        sensor.GloBirdServiceStatusSensor(FakeCoordinator(), entry, service),
        sensor.GloBirdMeterInfoSensor(FakeCoordinator(), entry, service),
        sensor.GloBirdLatestDataDateSensor(FakeCoordinator(), entry, service),
        sensor.GloBirdLatestDataStatusSensor(FakeCoordinator(), entry, service),
        sensor.GloBirdUsageTotalSensor(FakeCoordinator(), entry, service),
        sensor.GloBirdLatestDayUsageSensor(FakeCoordinator(), entry, service),
        sensor.GloBirdSolarExportTotalSensor(FakeCoordinator(), entry, service),
        sensor.GloBirdLatestDaySolarExportSensor(FakeCoordinator(), entry, service),
        sensor.GloBirdCostTotalSensor(FakeCoordinator(), entry, service),
        sensor.GloBirdLatestDayCostSensor(FakeCoordinator(), entry, service),
        sensor.GloBirdZeroHeroStatusSensor(FakeCoordinator(), entry, service),
        sensor.GloBirdExpectedMonthlyCostSensor(FakeCoordinator(), entry, service),
        sensor.GloBirdBillingPeriodDaysSensor(FakeCoordinator(), entry, service),
        sensor.GloBirdBillingPeriodCostSensor(FakeCoordinator(), entry, service),
        sensor.GloBirdWeatherSummarySensor(FakeCoordinator(), entry, service),
    ]

    values = [entity.native_value for entity in created]
    assert "Switched" in values
    assert "SMART" in values
    assert "2026/07/01" in values
    assert "ready" in values
    assert 10.5 in values
    assert 1.2 in values
    assert 3.4 in values
    assert 0.3 in values
    assert 12.5 in values
    assert 1.1 in values
    assert "achieved" in values
    assert 27 in values

    # Touch attributes for branch coverage across sensor classes.
    for entity in created:
        attrs = entity.extra_state_attributes
        assert "service_type" in attrs


def test_async_setup_entry_adds_global_account_and_service_entities() -> None:
    """Setup should create entity instances for global, account, and service sensors."""

    class FakeCoordinator(ListenerMixin):
        data = {
            "accounts": [
                {
                    "accountId": 1,
                    "accountNumber": "A1",
                    "service_count": 1,
                }
            ],
            "services": [
                {
                    "accountServiceId": 810965,
                    "serviceType": "Power",
                    "siteIdentifier": "NMI-1",
                }
            ],
            "service_data": {
                "810965": {
                    "service": {
                        "accountServiceId": 810965,
                        "serviceType": "Power",
                        "siteIdentifier": "NMI-1",
                    },
                    "usage_summary": {},
                    "cost_summary": {},
                    "latest_data_status": {},
                    "weather_summary": {},
                }
            },
        }

    hass = {
        sensor.DOMAIN: {
            "entry-1": FakeCoordinator(),
        }
    }

    captured: list[Any] = []

    def add_entities(entities: list[Any]) -> None:
        captured.extend(entities)

    entry = FakeEntry()
    asyncio.run(
        sensor.async_setup_entry(
            types.SimpleNamespace(data=hass),
            entry,
            add_entities,
        )
    )

    assert captured
    # Existing entity unique IDs must not change.
    assert {entity.unique_id for entity in captured} == {
        "entry-1_balance",
        "entry-1_dashboard_balance",
        "entry-1_latest_invoice",
        "entry-1_signup_services",
        "entry-1_last_successful_refresh",
        "entry-1_refresh_status",
        "entry-1_account_1_summary",
        *(
            f"entry-1_service_810965_{key}"
            for key in (
                "service_status",
                "meter_info",
                "latest_data_date",
                "latest_data_status",
                "usage_total",
                "latest_day_usage",
                "solar_export_total",
                "latest_day_solar_export",
                "cost_total",
                "latest_day_cost",
                "solar_export_credit_total",
                "latest_day_solar_export_credit",
                "zerohero_status",
                "expected_month_cost",
                "billing_period_days",
                "billing_period_cost",
                "weather_summary",
            )
        ),
    }
    assert len(entry.unload_callbacks) == 1
    assert any(isinstance(entity, sensor.GloBirdGlobalSensor) for entity in captured)
    assert any(
        isinstance(entity, sensor.GloBirdAccountSummarySensor) for entity in captured
    )


def test_global_helper_fallback_branches_without_global_summary() -> None:
    """Helper fallbacks should work when API global summary is unavailable."""
    data = {
        "dashboard": {
            "data": {
                "currentBalance": 2.5,
                "accountId": 1,
                "accountNumber": "A1",
                "lastestCorrespondence": {"id": 1},
                "lastestInvoice": {"amount": 5.5},
                "recentAccountTransactions": [{"id": "t1"}],
            }
        },
        "balance": {
            "data": {
                "balance": 3.1,
                "maxRefundableAmount": 1,
                "showRefundableAmount": True,
            }
        },
        "signup_info": {"data": [1]},
        "last_update": 1700000000,
    }

    assert sensor._balance_value(data) == -3.1
    assert sensor._dashboard_balance_value(data) == -2.5
    assert sensor._latest_invoice_value(data) == 5.5
    assert sensor._signup_services_value(data) == 1
    assert sensor._refresh_status_value(data) == "ok"
    assert sensor._dashboard_attrs(data)["account_number"] == "A1"
    assert sensor._latest_invoice_attrs(data)["amount"] == 5.5


def test_account_summary_returns_empty_when_account_missing() -> None:
    """Account summary entity should gracefully handle missing account rows."""

    class FakeCoordinator:
        data = {"accounts": []}

    entity = sensor.GloBirdAccountSummarySensor(
        FakeCoordinator(),
        types.SimpleNamespace(entry_id="entry-1"),
        {"accountId": 123, "accountNumber": "A123"},
    )
    assert entity.native_value is None
    assert entity.extra_state_attributes == {"globird_sensor_key": "account_summary"}


def test_zerohero_boundary_scheduling_and_callbacks(monkeypatch: Any) -> None:
    """ZeroHero sensor should schedule and cancel boundary callbacks."""

    scheduled = {}

    def fake_track(_hass: Any, callback: Any, when: Any) -> Any:
        scheduled["callback"] = callback
        scheduled["when"] = when

        def unsub() -> None:
            scheduled["unsub_called"] = True

        return unsub

    monkeypatch.setattr(sensor, "async_track_point_in_time", fake_track)

    class FakeCoordinator:
        data = {
            "service_data": {
                "1": {"service": {"accountServiceId": 1}, "cost_summary": {}}
            }
        }

    entity = sensor.GloBirdZeroHeroStatusSensor(
        FakeCoordinator(),
        types.SimpleNamespace(entry_id="entry-1"),
        {"accountServiceId": 1, "serviceType": "Power"},
    )
    entity.hass = types.SimpleNamespace()

    asyncio.run(entity.async_added_to_hass())
    assert "when" in scheduled

    entity._handle_zerohero_boundary_update(datetime.now(UTC))
    entity._cancel_zerohero_boundary_update()
    assert scheduled.get("unsub_called") is True


def test_gas_statistics_import_paths(monkeypatch: Any) -> None:
    """Gas statistics uploader should handle success and add failures safely."""

    class FakeCoordinator:
        data = {
            "service_data": {
                "123": {
                    "service": {"accountServiceId": 123, "serviceType": "Gas"},
                    "gas_reading_summary": {
                        "history": [
                            {"date": "2026-01-01", "read_index": 100.0, "serial": "x"},
                            {"date": "2026-01-02", "read_index": 101.0, "serial": "x"},
                        ],
                        "latest_reading": 101.0,
                    },
                }
            }
        }

    entity = sensor.GloBirdLatestGasReadingSensor(
        FakeCoordinator(),
        types.SimpleNamespace(entry_id="entry-1"),
        {"accountServiceId": 123, "serviceType": "Gas"},
    )
    entity.hass = types.SimpleNamespace(async_create_task=lambda _coro: None)

    recorder_statistics = types.ModuleType(
        "homeassistant.components.recorder.statistics"
    )

    class StatisticData(dict):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

    class StatisticMetaData(dict):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)

    async def add_ok(_hass: Any, _meta: Any, _stats: Any) -> None:
        return None

    recorder_statistics.StatisticData = StatisticData
    recorder_statistics.StatisticMetaData = StatisticMetaData
    recorder_statistics.async_add_external_statistics = add_ok
    recorder_statistics.statistics_during_period = lambda *_args: {}
    sys.modules["homeassistant.components.recorder.statistics"] = recorder_statistics

    class FakeRecorder:
        async def async_add_executor_job(self, func: Any, *args: Any) -> Any:
            return func(*args)

    helpers_recorder = types.ModuleType("homeassistant.helpers.recorder")
    helpers_recorder.get_instance = lambda _hass: FakeRecorder()
    monkeypatch.setitem(sys.modules, "homeassistant.helpers.recorder", helpers_recorder)

    asyncio.run(entity._async_upload_historical_statistics())

    async def add_fail(_hass: Any, _meta: Any, _stats: Any) -> None:
        raise RuntimeError("fail")

    recorder_statistics.async_add_external_statistics = add_fail
    asyncio.run(entity._async_upload_historical_statistics())


def test_latest_data_status_fallback_and_billing_start_invalid() -> None:
    """Fallback status and invalid billing date should be handled gracefully."""
    status = sensor._latest_data_status({"usage_summary": {}, "cost_summary": {}})
    assert status["status"] == "no_data"
    assert (
        sensor._billing_period_start(
            {"dashboard": {"data": {"lastestInvoice": {"issuedDate": "bad"}}}}
        )
        is None
    )


def test_billing_period_cost_sensor_fallbacks() -> None:
    """Billing period cost sensor should return fallback totals when no start date."""

    service = {"accountServiceId": 1, "serviceType": "Power", "siteIdentifier": "NMI"}

    class FakeCoordinator:
        data = {
            "dashboard": {"data": {"lastestInvoice": {}}},
            "service_data": {
                "1": {
                    "service": service,
                    "cost_summary": {
                        "total_amount": 4.2,
                        "daily_totals": [{"date": "2026/01/01", "amount": 4.2}],
                    },
                }
            },
        }

    entity = sensor.GloBirdBillingPeriodCostSensor(
        FakeCoordinator(),
        types.SimpleNamespace(entry_id="entry-1"),
        service,
    )
    assert entity.native_value == 4.2
    assert entity.last_reset is None


def test_energy_dashboard_sensors_and_external_statistics(monkeypatch: Any) -> None:
    """Test Energy Dashboard usage, solar export, cost, and solar credit sensors and external stats."""
    service = {"accountServiceId": 1, "serviceType": "Power", "siteIdentifier": "NMI-1"}
    gas_service = {
        "accountServiceId": 2,
        "serviceType": "Gas",
        "siteIdentifier": "MIRN-1",
    }

    class FakeCoordinator(ListenerMixin):
        data = {
            "last_update": 1700000000.0,
            "dashboard": {
                "data": {"lastestInvoice": {"issuedDate": "2026-09-01T00:00:00"}}
            },
            "accounts": [
                {"accountId": 10, "accountNumber": "ACC-10", "service_count": 2}
            ],
            "services": [service, gas_service],
            "service_data": {
                "1": {
                    "service": service,
                    "usage_summary": {
                        "total_usage": 120.5,
                        "latest_day": "2026-09-27",
                        "latest_day_usage": 14.2,
                        "daily": [{"readDate": "2026-09-27", "usage": 14.2}],
                        "total_export": 45.0,
                        "latest_day_export": 6.5,
                        "export_daily": [{"readDate": "2026-09-27", "usage": 6.5}],
                        "registers": [],
                    },
                    "cost_summary": {
                        "total_amount": 32.10,
                        "total_import_cost": 36.10,
                        "total_export_credit": 4.00,
                        "latest_day": "2026-09-27",
                        "latest_day_amount": 3.50,
                        "latest_day_import_cost": 4.00,
                        "latest_day_export_credit": 0.50,
                        "daily_totals": [{"date": "2026-09-27", "amount": 3.50}],
                        "daily_export_credit_totals": [
                            {"date": "2026-09-27", "amount": 0.50}
                        ],
                    },
                },
                "2": {
                    "service": gas_service,
                    "gas_reading_summary": {
                        "latest_reading": 250.0,
                        "latest_reading_date": "2026-09-26",
                        "latest_reading_source": "Basic",
                        "latest_reading_serial": "G1",
                        "latest_reading_quality_method": "Actual",
                        "history": [],
                    },
                    "cost_summary": {
                        "total_amount": 18.00,
                        "latest_day": "2026-09-26",
                        "latest_day_amount": 1.20,
                        "daily_totals": [{"date": "2026-09-26", "amount": 1.20}],
                    },
                },
            },
        }

    uploaded, _queries = _install_recorder_stubs(monkeypatch, [])
    recorder_statistics = sys.modules["homeassistant.components.recorder.statistics"]

    entry = FakeEntry(runtime_data=FakeCoordinator())
    added_entities: list[Any] = []
    asyncio.run(
        sensor.async_setup_entry(
            types.SimpleNamespace(data={sensor.DOMAIN: {"entry-1": FakeCoordinator()}}),
            entry,
            added_entities.extend,
        )
    )
    assert len(added_entities) >= 25

    for ent in added_entities:
        ent.hass = types.SimpleNamespace(
            async_create_task=lambda coro: asyncio.run(coro)
        )
        _ = ent.native_value
        _ = ent.extra_state_attributes
        if hasattr(ent, "last_reset"):
            _ = ent.last_reset
        asyncio.run(ent.async_added_to_hass())
        for upload, _name in entry.background_tasks:
            asyncio.run(upload)
        entry.background_tasks.clear()
        ent._handle_coordinator_update()

    assert len(uploaded) >= 4

    # Test external statistics error handling and empty/invalid rows
    assert (
        sensor._build_daily_cumulative_statistics(
            ["not-a-dict", {"date": "invalid", "amount": 1.0}],
            date_key="date",
            value_key="amount",
            tzinfo=UTC,
        )
        == []
    )

    async def add_err(_hass: Any, _meta: Any, _stats: Any) -> None:
        raise RuntimeError("db error")

    recorder_statistics.async_add_external_statistics = add_err
    usage_sensor = sensor.GloBirdUsageTotalSensor(FakeCoordinator(), entry, service)
    usage_sensor.hass = types.SimpleNamespace()
    asyncio.run(usage_sensor._async_upload_statistics())

    # Test global summary vs raw fallback functions
    raw_data = {
        "balance": {
            "data": {
                "balance": 10.0,
                "maxRefundableAmount": 5.0,
                "showRefundableAmount": True,
            }
        },
        "dashboard": {
            "data": {
                "currentBalance": 20.0,
                "accountId": 1,
                "accountNumber": "A1",
                "lastestInvoice": {"amount": 50.0},
                "recentAccountTransactions": [{"id": 1}],
            }
        },
        "signup_info": {"data": [{"id": 1}]},
        "last_update": "bad-timestamp",
    }
    assert sensor._balance_value(raw_data) == -10.0
    assert sensor._balance_attrs(raw_data)["max_refundable_amount"] == 5.0
    assert sensor._dashboard_balance_value(raw_data) == -20.0
    assert sensor._dashboard_attrs(raw_data)["account_id"] == 1
    assert sensor._latest_invoice_value(raw_data) == 50.0
    assert sensor._latest_invoice_attrs(raw_data)["amount"] == 50.0
    assert sensor._signup_services_value(raw_data) == 1
    assert len(sensor._signup_services_attrs(raw_data)["signup_info"]) == 1
    assert sensor._timestamp_value("bad-timestamp") is None
    assert sensor._refresh_status_value({"refresh_error": "boom"}) == "error"
    assert (
        sensor._refresh_status_attrs({"refresh_error": "boom"})["refresh_error"]
        == "boom"
    )

    summary_data = {
        "global_summary": {
            "balance": -12.3,
            "max_refundable_amount": 3.0,
            "show_refundable_amount": False,
            "dashboard_balance": -4.5,
            "dashboard": {"account_id": 99},
            "latest_invoice_amount": 88.0,
            "latest_invoice": {"amount": 88.0},
            "signup_services": 2,
            "signup_info": [{"id": 1}, {"id": 2}],
            "refresh_status": "ok",
            "last_successful_refresh": 1700000000.0,
            "last_failed_refresh": None,
            "refresh_error": None,
            "fetch_errors": {},
        }
    }
    assert sensor._balance_value(summary_data) == -12.3
    assert sensor._balance_attrs(summary_data)["max_refundable_amount"] == 3.0
    assert sensor._dashboard_balance_value(summary_data) == -4.5
    assert sensor._dashboard_attrs(summary_data)["account_id"] == 99
    assert sensor._latest_invoice_value(summary_data) == 88.0
    assert sensor._latest_invoice_attrs(summary_data)["amount"] == 88.0
    assert sensor._signup_services_value(summary_data) == 2
    assert len(sensor._signup_services_attrs(summary_data)["signup_info"]) == 2
    assert sensor._refresh_status_value(summary_data) == "ok"
    assert sensor._refresh_status_attrs(summary_data)["refresh_error"] is None
    assert sensor._parse_portal_day("   ") is None
    assert sensor._day_reset_timestamp(None) is None
    assert sensor._billing_period_completed_days({}) is None
    assert sensor._service_name_suffix({}) == "unknown"
    assert sensor._safe_statistic_id("!!!", "!!!") == "service"
    assert sensor._safe_statistic_id("", "123") == "svc_123"
    assert sensor._build_gas_statistics([], tzinfo=UTC) == []


def test_daily_cumulative_statistics_continue_from_stored_sum() -> None:
    """A stored sum before the window seeds the running total (#21)."""
    statistics = sensor._build_daily_cumulative_statistics(
        [
            {"readDate": "2026-09-26", "usage": 3.5},
            {"readDate": "2026-09-27", "usage": 4.25},
        ],
        date_key="readDate",
        value_key="usage",
        tzinfo=UTC,
        stored_sum=10.0,
    )

    assert [row["state"] for row in statistics] == [3.5, 4.25]
    assert [row["sum"] for row in statistics] == [13.5, 17.75]


_POWER_SERVICE = {"accountServiceId": 1, "serviceType": "Power", "siteIdentifier": "N1"}


class _UsageCoordinator(ListenerMixin):
    """Coordinator stand-in holding one electricity service's usage summary."""

    last_update_success = True

    def __init__(self, usage_summary: dict[str, Any]) -> None:
        self.data: dict[str, Any] = {
            "services": [_POWER_SERVICE],
            "service_data": {
                "1": {"service": _POWER_SERVICE, "usage_summary": usage_summary}
            },
        }

    def set_summary(self, usage_summary: dict[str, Any]) -> None:
        self.data["service_data"]["1"]["usage_summary"] = usage_summary


def _usage_total_entity(daily: list[dict[str, Any]]) -> Any:
    """Return a Recent Usage Total entity for the given daily rows."""
    return sensor.GloBirdUsageTotalSensor(
        _UsageCoordinator({"daily": daily}), FakeEntry(), _POWER_SERVICE
    )


_DAILY = [
    {"readDate": "2026/10/01", "usage": 2.0},
    {"readDate": "2026/10/02", "usage": 3.0},
]


def test_daily_upload_first_import_starts_at_first_day(monkeypatch: Any) -> None:
    """Without stored rows the first sum is the first day's usage."""
    uploaded, queries = _install_recorder_stubs(monkeypatch, [])

    asyncio.run(_usage_total_entity(_DAILY)._async_upload_statistics())

    metadata, rows = uploaded[0]
    assert metadata["statistic_id"] == "globird:entry_1_service_1_usage_total"
    assert [row["sum"] for row in rows] == [2.0, 5.0]
    assert queries[0][3] == {metadata["statistic_id"]}
    assert queries[0][2] == rows[0]["start"]
    assert queries[0][6] == {"sum"}


def test_daily_upload_continues_from_stored_row(monkeypatch: Any) -> None:
    """The last stored row before the window anchors the uploaded sums."""
    uploaded, _queries = _install_recorder_stubs(
        monkeypatch,
        [
            {"start": 1.0, "state": 1.0, "sum": 40.0},
            {"start": 2.0, "state": None, "sum": 50.5},
            {"start": 3.0, "state": 1.0, "sum": None},
        ],
    )

    asyncio.run(_usage_total_entity(_DAILY)._async_upload_statistics())

    assert [row["sum"] for row in uploaded[0][1]] == [52.5, 55.5]


def test_daily_upload_ignores_stored_rows_without_sum(monkeypatch: Any) -> None:
    """Stored rows without a sum do not anchor the upload."""
    uploaded, _queries = _install_recorder_stubs(
        monkeypatch, [{"start": 1.0, "state": 1.0, "sum": None}]
    )

    asyncio.run(_usage_total_entity(_DAILY)._async_upload_statistics())

    assert [row["sum"] for row in uploaded[0][1]] == [2.0, 5.0]


def test_daily_upload_skipped_when_stored_rows_unreadable(monkeypatch: Any) -> None:
    """An unreadable recorder skips the import instead of rewriting rows."""
    uploaded, _queries = _install_recorder_stubs(
        monkeypatch, RuntimeError("database locked")
    )

    asyncio.run(_usage_total_entity(_DAILY)._async_upload_statistics())

    assert uploaded == []


def test_daily_upload_continues_when_window_moves(monkeypatch: Any) -> None:
    """Two refreshes whose windows differ by a day keep one continuous sum."""
    stored: list[dict[str, Any]] = []
    uploaded, _queries = _install_recorder_stubs(monkeypatch, stored)

    asyncio.run(_usage_total_entity(_DAILY)._async_upload_statistics())
    first_rows = uploaded[0][1]
    # The recorder keeps day 1; the next window starts at day 2.
    stored.append(
        {
            "start": first_rows[0]["start"].timestamp(),
            "state": first_rows[0]["state"],
            "sum": first_rows[0]["sum"],
        }
    )
    asyncio.run(
        _usage_total_entity(
            [*_DAILY[1:], {"readDate": "2026/10/03", "usage": 4.0}]
        )._async_upload_statistics()
    )

    assert [row["sum"] for row in uploaded[1][1]] == [5.0, 9.0]


def _zerohero_usage_summary() -> dict[str, Any]:
    """Return the usage summary built from the redacted live ZEROHERO fixture."""
    fixtures = json.loads(ZEROHERO_FIXTURE_PATH.read_text())
    return client_module.build_usage_summary(fixtures["electricity_usage"])


def _setup_usage_entities(coordinator: Any) -> tuple[list[Any], FakeEntry]:
    """Run sensor setup and return the usage entities it added."""
    entry = FakeEntry(runtime_data=coordinator)
    added: list[Any] = []
    asyncio.run(
        sensor.async_setup_entry(types.SimpleNamespace(data={}), entry, added.extend)
    )
    return added, entry


def _register_entities(entities: list[Any]) -> dict[str, Any]:
    """Return per-register and controlled-load entities keyed by unique ID."""
    return {
        entity.unique_id: entity
        for entity in entities
        if isinstance(
            entity,
            (
                sensor.GloBirdUsageRegisterSensor,
                sensor.GloBirdControlledLoadTotalSensor,
                sensor.GloBirdLatestDayControlledLoadSensor,
            ),
        )
    }


def test_setup_adds_register_sensors_for_time_of_use_registers(
    monkeypatch: Any,
) -> None:
    """Live ZEROHERO shape: one sensor per TOU import and feed-in window (#18)."""
    coordinator = _UsageCoordinator(_zerohero_usage_summary())
    added, _entry = _setup_usage_entities(coordinator)
    registers = _register_entities(added)

    assert sorted(registers) == [
        "entry-1_service_1_register_b1_solar_generation_feed_in_11pm_4pm",
        "entry-1_service_1_register_b1_solar_generation_feed_in_4pm_11pm",
        "entry-1_service_1_register_e1_offpeak_usage",
        "entry-1_service_1_register_e1_peak_usage",
        "entry-1_service_1_register_e1_shoulder_usage",
    ]
    offpeak = registers["entry-1_service_1_register_e1_offpeak_usage"]
    assert offpeak._attr_name == "Recent E1 Offpeak Usage"
    assert offpeak.available is True
    assert offpeak.native_value == 0.082
    attrs = offpeak.extra_state_attributes
    assert attrs["time_periods"] == [{"start": "12:00", "end": "15:00"}]
    assert attrs["usage_class"] == "general_import"
    assert attrs["latest_day"] == "2026/10/16"
    assert attrs["daily_count"] == 3
    feed_in = registers[
        "entry-1_service_1_register_b1_solar_generation_feed_in_4pm_11pm"
    ]
    assert feed_in._attr_icon == "mdi:solar-power"
    assert feed_in._attr_name == "Recent B1 Solar/Generation Feed in (4pm-11pm)"

    uploaded, _queries = _install_recorder_stubs(monkeypatch, [])
    asyncio.run(offpeak._async_upload_statistics())
    metadata, rows = uploaded[0]
    assert metadata["statistic_id"] == (
        "globird:entry_1_service_1_register_e1_offpeak_usage"
    )
    assert metadata["name"] == "Recent E1 Offpeak Usage"
    assert [row["state"] for row in rows] == [0.078, 0.002, 0.002]
    assert [row["sum"] for row in rows] == [0.078, 0.08, 0.082]


def test_setup_adds_no_register_sensors_for_flat_rate() -> None:
    """Flat-rate accounts (one register per class) get no extra sensors."""
    summary = client_module.build_usage_summary(
        {
            "data": [
                {
                    "readDate": "2026/10/01",
                    "usage": 1.0,
                    "suffix": "E1",
                    "chargeType": "Usage",
                    "chargeCategoryCode": "USAGE",
                },
                {
                    "readDate": "2026/10/01",
                    "usage": 2.0,
                    "suffix": "B1",
                    "chargeType": "Feed in",
                    "chargeCategoryCode": "SOLAR",
                },
            ]
        }
    )

    added, _entry = _setup_usage_entities(_UsageCoordinator(summary))

    assert _register_entities(added) == {}


def test_controlled_load_sensors_follow_controlled_load_registers(
    monkeypatch: Any,
) -> None:
    """Controlled-load sensors exist only once the portal returns such a register."""
    flat = client_module.build_usage_summary(
        {
            "data": [
                {
                    "readDate": "2026/10/01",
                    "usage": 5.0,
                    "suffix": "E1",
                    "chargeType": "Usage",
                    "chargeCategoryCode": "USAGE",
                }
            ]
        }
    )
    controlled = client_module.build_usage_summary(
        {
            "data": [
                {
                    "readDate": "2026/10/01",
                    "usage": 5.0,
                    "suffix": "E1",
                    "chargeType": "Usage",
                    "chargeCategoryCode": "USAGE",
                },
                {
                    "readDate": "2026/10/01",
                    "usage": 2.5,
                    "suffix": "E2",
                    "chargeType": "Controlled Load",
                    "chargeCategoryCode": "CONTROL",
                },
            ]
        }
    )
    coordinator = _UsageCoordinator(flat)
    added: list[Any] = []
    entry = FakeEntry(runtime_data=coordinator)
    asyncio.run(
        sensor.async_setup_entry(types.SimpleNamespace(data={}), entry, added.extend)
    )
    assert _register_entities(added) == {}

    # A refresh that returns the controlled-load register adds its sensors once.
    coordinator.set_summary(controlled)
    for listener in list(coordinator.listeners):
        listener()
        listener()
    new = _register_entities(added)
    assert sorted(new) == [
        "entry-1_service_1_controlled_load_total",
        "entry-1_service_1_latest_day_controlled_load",
    ]
    total = new["entry-1_service_1_controlled_load_total"]
    latest = new["entry-1_service_1_latest_day_controlled_load"]
    assert total.native_value == 2.5
    assert [r["key"] for r in total.extra_state_attributes["registers"]] == [
        "E2-Controlled Load"
    ]
    assert latest.native_value == 2.5
    assert latest.last_reset is not None
    assert latest.extra_state_attributes["daily_count"] == 1
    usage_total = sensor.GloBirdUsageTotalSensor(coordinator, entry, _POWER_SERVICE)
    assert usage_total.native_value == 5.0
    uploaded, _queries = _install_recorder_stubs(monkeypatch, [])
    asyncio.run(total._async_upload_statistics())
    assert uploaded[0][0]["statistic_id"] == (
        "globird:entry_1_service_1_controlled_load_total"
    )
    assert [row["sum"] for row in uploaded[0][1]] == [2.5]

    # Unloading the entry removes the listener.
    entry.unload_callbacks[0]()
    assert coordinator.listeners == []


def test_register_sensor_unavailable_while_register_missing(monkeypatch: Any) -> None:
    """A register that disappears makes its entity unavailable, not an error."""
    summary = _zerohero_usage_summary()
    coordinator = _UsageCoordinator(summary)
    added, _entry = _setup_usage_entities(coordinator)
    peak = _register_entities(added)["entry-1_service_1_register_e1_peak_usage"]
    uploaded, _queries = _install_recorder_stubs(monkeypatch, [])

    coordinator.set_summary(
        {
            **summary,
            "registers": [
                register
                for register in summary["registers"]
                if register["slug"] != "e1_peak_usage"
            ],
        }
    )
    for listener in coordinator.listeners:
        listener()

    assert peak.available is False
    assert peak.native_value is None
    assert peak.extra_state_attributes["register_key"] is None
    asyncio.run(peak._async_upload_statistics())
    assert uploaded == []
    assert len(_register_entities(added)) == 5

    coordinator.set_summary(summary)
    assert peak.available is True
    coordinator.last_update_success = False
    assert peak.available is False


def test_dynamic_usage_entities_skip_gas_and_missing_details() -> None:
    """Discovery ignores gas services and services without usage data."""
    gas = {"accountServiceId": 2, "serviceType": "Gas"}

    class Coordinator:
        data = {
            "services": [gas, {"accountServiceId": 3, "serviceType": "Power"}],
            "service_data": {"2": {"usage_summary": {"registers": []}}, "3": None},
        }

    assert (
        sensor._dynamic_usage_entities(Coordinator(), FakeEntry(), set()) == []  # type: ignore[arg-type]
    )


def test_daily_statistics_sensor_requires_upload_implementation() -> None:
    """The shared daily statistics base has no series of its own."""
    entity = sensor.GloBirdDailyStatisticsSensor(
        _UsageCoordinator({}), FakeEntry(), _POWER_SERVICE
    )
    try:
        asyncio.run(entity._async_upload_statistics())
    except NotImplementedError:
        pass
    else:
        raise AssertionError("expected NotImplementedError")


def test_daily_statistics_uploads_run_one_at_a_time() -> None:
    """Overlapping uploads of one entity are serialised (anchor read + write)."""
    events: list[str] = []

    class Sensor(sensor.GloBirdDailyStatisticsSensor):
        async def _async_upload_statistics(self) -> None:
            events.append("start")
            await asyncio.sleep(0)
            events.append("end")

    entry = FakeEntry()
    entity = Sensor(_UsageCoordinator({}), entry, _POWER_SERVICE)

    async def run_two() -> None:
        tasks: list[Any] = []
        entity.hass = types.SimpleNamespace(
            async_create_task=lambda coro: tasks.append(asyncio.ensure_future(coro))
        )
        await entity.async_added_to_hass()
        tasks.extend(asyncio.ensure_future(coro) for coro, _ in entry.background_tasks)
        entity._handle_coordinator_update()
        await asyncio.gather(*tasks)

    asyncio.run(run_two())

    assert events == ["start", "end", "start", "end"]


def test_daily_upload_waits_for_recorder_commit(monkeypatch: Any) -> None:
    """The upload waits for the queued import to commit before returning."""
    _install_recorder_stubs(monkeypatch, [])
    events: list[str] = []

    async def run() -> None:
        loop = asyncio.get_running_loop()
        future = loop.create_future()

        class Recorder:
            async def async_add_executor_job(self, func: Any, *args: Any) -> Any:
                return func(*args)

            def async_get_commit_future(self) -> Any:
                events.append("commit requested")
                loop.call_soon(
                    lambda: (events.append("committed"), future.set_result(None))
                )
                return future

        sys.modules["homeassistant.helpers.recorder"].get_instance = lambda _hass: (
            Recorder()
        )
        await _usage_total_entity(_DAILY)._async_upload_statistics()
        events.append("upload returned")

    asyncio.run(run())

    assert events == ["commit requested", "committed", "upload returned"]


def test_daily_upload_commit_wait_is_bounded(monkeypatch: Any) -> None:
    """A recorder that never commits does not block the upload forever."""
    uploaded, _queries = _install_recorder_stubs(monkeypatch, [])
    monkeypatch.setattr(sensor, "RECORDER_COMMIT_TIMEOUT", 0)

    async def run() -> None:
        never = asyncio.get_running_loop().create_future()

        class Recorder:
            async def async_add_executor_job(self, func: Any, *args: Any) -> Any:
                return func(*args)

            def async_get_commit_future(self) -> Any:
                return never

        sys.modules["homeassistant.helpers.recorder"].get_instance = lambda _hass: (
            Recorder()
        )
        await _usage_total_entity(_DAILY)._async_upload_statistics()

    asyncio.run(run())

    assert len(uploaded) == 1


def test_daily_upload_ignores_stored_rows_without_start(monkeypatch: Any) -> None:
    """A stored row without a start time cannot anchor the upload."""
    uploaded, _queries = _install_recorder_stubs(
        monkeypatch, [{"start": None, "state": 1.0, "sum": 99.0}]
    )

    asyncio.run(_usage_total_entity(_DAILY)._async_upload_statistics())

    assert [row["sum"] for row in uploaded[0][1]] == [2.0, 5.0]


def test_daily_statistics_update_without_task_support_skips_upload(
    monkeypatch: Any,
) -> None:
    """A coordinator update without ``async_create_task`` uploads nothing."""
    uploaded, _queries = _install_recorder_stubs(monkeypatch, [])
    entity = _usage_total_entity(_DAILY)
    entity.hass = types.SimpleNamespace()

    entity._handle_coordinator_update()

    assert uploaded == []


def test_controlled_load_sensors_without_values() -> None:
    """Controlled-load sensors fall back cleanly when no value or day exists."""
    coordinator = _UsageCoordinator(
        {"total_controlled_load": None, "controlled_load_daily": []}
    )
    total = sensor.GloBirdControlledLoadTotalSensor(
        coordinator, FakeEntry(), _POWER_SERVICE
    )
    latest = sensor.GloBirdLatestDayControlledLoadSensor(
        coordinator, FakeEntry(), _POWER_SERVICE
    )

    assert total.native_value == 0.0
    assert latest.native_value is None
    assert latest.last_reset is None
    coordinator.set_summary({"controlled_load_daily": ["not-a-row"]})
    assert latest.last_reset is None

    coordinator.data["service_data"] = {}
    assert total.native_value is None


def test_usage_register_sensor_name_falls_back_to_slug() -> None:
    """A register without suffix or charge type is named after its slug."""
    entity = sensor.GloBirdUsageRegisterSensor(
        _UsageCoordinator({"registers": ["not-a-register"]}),
        FakeEntry(),
        _POWER_SERVICE,
        {"slug": "unknown"},
    )

    assert entity._attr_name == "Recent unknown"
    assert entity._attr_unique_id == "entry-1_service_1_register_unknown"
    assert entity._attr_icon == "mdi:chart-timeline-variant"
    assert entity.available is False


def test_daily_upload_accepts_synchronous_recorder_api(monkeypatch: Any) -> None:
    """A non-awaitable ``async_add_external_statistics`` result is accepted."""
    _install_recorder_stubs(monkeypatch, [])
    calls: list[Any] = []
    statistics_module = sys.modules["homeassistant.components.recorder.statistics"]
    monkeypatch.setattr(
        statistics_module,
        "async_add_external_statistics",
        lambda _hass, meta, stats: calls.append((meta, stats)),
    )

    asyncio.run(_usage_total_entity(_DAILY)._async_upload_statistics())

    assert [row["sum"] for row in calls[0][1]] == [2.0, 5.0]


def _deferred_start(monkeypatch: Any) -> list[Any]:
    """Hold ``async_at_started`` callbacks until the test releases them."""
    started: list[Any] = []

    def at_started(hass: Any, at_start_cb: Any) -> Any:
        started.append(lambda: at_start_cb(hass))
        return lambda: None

    monkeypatch.setattr(sensor, "async_at_started", at_started)
    return started


def test_daily_statistics_upload_waits_for_started_not_setup(
    monkeypatch: Any,
) -> None:
    """Entity setup never runs the upload; it starts in the background later."""
    started = _deferred_start(monkeypatch)
    events: list[str] = []

    class Sensor(sensor.GloBirdDailyStatisticsSensor):
        async def _async_upload_statistics(self) -> None:
            events.append("upload")

    entry = FakeEntry()
    background = entry.background_tasks
    entity = Sensor(_UsageCoordinator({}), entry, _POWER_SERVICE)
    entity.entity_id = "sensor.globird_usage"
    entity.hass = types.SimpleNamespace()

    asyncio.run(entity.async_added_to_hass())
    assert events == []
    assert background == []
    assert len(started) == 1
    assert len(entity._remove_callbacks) == 1

    started[0]()
    assert len(background) == 1
    upload, name = background[0]
    assert name == "globird daily statistics upload sensor.globird_usage"
    asyncio.run(upload)
    assert events == ["upload"]


def test_gas_statistics_upload_waits_for_started_not_setup(
    monkeypatch: Any,
) -> None:
    """The gas history upload also starts in the background once started."""
    started = _deferred_start(monkeypatch)
    events: list[str] = []
    entry = FakeEntry()
    background = entry.background_tasks

    async def upload(_self: Any) -> None:
        events.append("upload")

    monkeypatch.setattr(
        sensor.GloBirdLatestGasReadingSensor,
        "_async_upload_historical_statistics",
        upload,
    )
    entity = sensor.GloBirdLatestGasReadingSensor(
        _UsageCoordinator({}),
        entry,
        {"accountServiceId": 123, "serviceType": "Gas"},
    )
    entity.entity_id = "sensor.globird_gas"
    entity.hass = types.SimpleNamespace()

    asyncio.run(entity.async_added_to_hass())
    assert events == []
    assert background == []

    started[0]()
    upload_coro, name = background[0]
    assert name == "globird gas statistics upload sensor.globird_gas"
    asyncio.run(upload_coro)
    assert events == ["upload"]


def test_gas_statistics_uploads_run_one_at_a_time(monkeypatch: Any) -> None:
    """The startup gas upload and a refresh upload never interleave."""
    events: list[str] = []

    async def upload(_self: Any) -> None:
        events.append("start")
        await asyncio.sleep(0)
        events.append("end")

    monkeypatch.setattr(
        sensor.GloBirdLatestGasReadingSensor,
        "_async_upload_historical_statistics",
        upload,
    )
    entry = FakeEntry()
    entity = sensor.GloBirdLatestGasReadingSensor(
        _UsageCoordinator({}),
        entry,
        {"accountServiceId": 123, "serviceType": "Gas"},
    )

    async def run_two() -> None:
        tasks: list[Any] = []
        entity.hass = types.SimpleNamespace(
            async_create_task=lambda coro: tasks.append(asyncio.ensure_future(coro))
        )
        await entity.async_added_to_hass()
        tasks.extend(asyncio.ensure_future(coro) for coro, _ in entry.background_tasks)
        entity._handle_coordinator_update()
        await asyncio.gather(*tasks)

    asyncio.run(run_two())

    assert events == ["start", "end", "start", "end"]


def test_gas_upload_waits_for_recorder_commit(monkeypatch: Any) -> None:
    """A successful gas import waits for the recorder commit."""
    uploaded, _queries = _install_recorder_stubs(monkeypatch, [])
    waited: list[str] = []

    async def wait(_self: Any, statistic_id: str) -> None:
        waited.append(statistic_id)

    monkeypatch.setattr(
        sensor.GloBirdServiceBaseSensor, "_async_wait_for_statistics_commit", wait
    )
    entity = _gas_reading_entity(_GAS_HISTORY)
    asyncio.run(entity._async_upload_historical_statistics())

    assert len(uploaded) == 1
    assert waited == [uploaded[0][0]["statistic_id"]]


def test_card_discovery_metadata_is_additive_and_unrecorded() -> None:
    """Stable discovery roles and external IDs survive entity renaming."""
    coordinator = types.SimpleNamespace(
        data={"service_data": {}}, last_update_success=True
    )
    entry = types.SimpleNamespace(entry_id="synthetic-entry")
    service = {
        "accountId": "demo",
        "accountServiceId": "electric",
        "serviceType": "Electricity",
    }
    for cls in (
        sensor.GloBirdUsageTotalSensor,
        sensor.GloBirdSolarExportTotalSensor,
        sensor.GloBirdControlledLoadTotalSensor,
        sensor.GloBirdCostTotalSensor,
        sensor.GloBirdSolarExportCreditTotalSensor,
        sensor.GloBirdLatestGasReadingSensor,
    ):
        entity = cls(coordinator, entry, service)
        entity.entity_id = "sensor.renamed_by_user"
        attrs = entity.extra_state_attributes
        assert attrs["globird_sensor_key"] == entity.sensor_key
        assert attrs["statistic_id"] == entity._external_statistic_id()
        assert attrs["statistic_id"].startswith("globird:")
        assert {"globird_sensor_key", "statistic_id"} <= entity._unrecorded_attributes
    daily = sensor.GloBirdLatestDayUsageSensor(coordinator, entry, service)
    assert "statistic_id" not in daily.extra_state_attributes
    global_entity = sensor.GloBirdGlobalSensor(
        coordinator, entry, sensor.GLOBAL_SENSORS[0]
    )
    assert global_entity.extra_state_attributes["globird_sensor_key"] == "balance"
    account = sensor.GloBirdAccountSummarySensor(
        coordinator, entry, {"accountId": "demo"}
    )
    assert account.extra_state_attributes["globird_sensor_key"] == "account_summary"
    register = sensor.GloBirdUsageRegisterSensor(
        coordinator, entry, service, {"slug": "peak"}
    )
    assert register.extra_state_attributes["globird_sensor_key"] == "register"
    assert (
        register.extra_state_attributes["statistic_id"]
        == register._external_statistic_id()
    )
