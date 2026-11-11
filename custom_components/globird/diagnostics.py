"""Diagnostics support for GloBird."""

from __future__ import annotations

import re
from math import isfinite
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .client import classify_usage_row, redact_sensitive, service_id
from .const import CONF_PASSWORD, DOMAIN

_REDACTED = "**REDACTED**"
_PORTAL_LABEL = re.compile(r"[A-Za-z0-9 _./:()&+\-]{1,64}")
_LONG_NUMBER = re.compile(r"\d{6}")
_OPTIONAL_ENDPOINTS = (
    "dashboard",
    "balance",
    "signup_info",
    "service_status",
    "meter_types",
    "read_meters",
    "weather_impacted_days",
)
_TEXT_FIELDS = frozenset(
    {
        "serviceType",
        "status",
        "refresh_status",
        "key",
        "slug",
        "suffix",
        "chargeType",
        "chargeCategory",
        "chargeCategoryCode",
        "direction",
        "usage_class",
        "readDate",
        "meterStatus",
        "minQualityMethod",
        "date",
        "dateAsDate",
        "start",
        "end",
        "month",
        "latest_day",
        "latest_available_day",
        "latest_ready_day",
        "latest_usage_day",
        "latest_cost_day",
        "latest_available_cost_day",
        "latest_reading_date",
        "latest_date",
        "latest_reading_quality_method",
        "quality_method",
    }
)
_REGISTER_FIELDS = ("suffix", "chargeType", "chargeCategoryCode", "direction")
_USAGE_DAY_FIELDS = ("readDate", "usage", "meterStatus", "minQualityMethod")
_COST_DAY_FIELDS = (
    "date",
    "amount",
    "quantity",
    "chargeCategory",
    "chargeType",
    "complete",
)


def _label(value: object) -> str | None:
    """Keep bounded, non-identifier-like portal labels."""
    if value is None:
        return None
    if (
        isinstance(value, str)
        and _PORTAL_LABEL.fullmatch(value)
        and not _LONG_NUMBER.search(value)
    ):
        return value
    return _REDACTED


def _mapping(value: Any) -> dict[str, Any]:
    """Return a portal object or an empty mapping for partial cached data."""
    return value if isinstance(value, dict) else {}


def _rows(value: Any) -> list[dict[str, Any]]:
    """Return only object rows from a portal array."""
    return (
        [row for row in value if isinstance(row, dict)]
        if isinstance(value, list)
        else []
    )


def _fields(value: Any, *names: str) -> dict[str, Any]:
    """Copy only named scalar fields, applying the portal label policy."""
    fields: dict[str, Any] = {}
    source = _mapping(value)
    for name in names:
        if name not in source:
            continue
        item = source[name]
        if name in _TEXT_FIELDS:
            fields[name] = _label(item)
        elif (
            item is None
            or isinstance(item, (bool, int))
            or (isinstance(item, float) and isfinite(item))
        ):
            fields[name] = item
    return fields


def _number(value: Any) -> float:
    """Return a finite measurement for an inventory total."""
    if isinstance(value, bool):
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return 0.0
    return number if isfinite(number) else 0.0


def _usage_inventory(payload: Any) -> list[dict[str, Any]]:
    """Group usage rows by register, retaining counts and range information."""
    groups: dict[tuple[str | None, ...], dict[str, Any]] = {}
    for row in _rows(_mapping(payload).get("data")):
        labels = tuple(_label(row.get(name)) for name in _REGISTER_FIELDS)
        usage_class = classify_usage_row(row)
        key = (*labels, usage_class)
        group = groups.get(key)
        if group is None:
            group = {
                **dict(zip(_REGISTER_FIELDS, labels, strict=True)),
                "usage_class": usage_class,
                "row_count": 0,
                "total_usage": 0.0,
                "first_read_date": None,
                "last_read_date": None,
                "interval_counts": [],
            }
            groups[key] = group
        group["row_count"] += 1
        group["total_usage"] += _number(row.get("usage"))
        if (read_date := _label(row.get("readDate"))) not in (None, _REDACTED):
            group["first_read_date"] = min(
                group["first_read_date"] or read_date, read_date
            )
            group["last_read_date"] = max(
                group["last_read_date"] or read_date, read_date
            )
        intervals = row.get("usageArray")
        if (
            isinstance(intervals, list)
            and len(intervals) not in group["interval_counts"]
        ):
            group["interval_counts"].append(len(intervals))
    for group in groups.values():
        group["interval_counts"].sort()
    return list(groups.values())


def _cost_inventory(payload: Any) -> list[dict[str, Any]]:
    """Group cost rows by charge category and type."""
    groups: dict[tuple[str | None, str | None], dict[str, Any]] = {}
    for row in _rows(_mapping(payload).get("data")):
        category, charge_type = (
            _label(row.get("chargeCategory")),
            _label(row.get("chargeType")),
        )
        key = (category, charge_type)
        group = groups.get(key)
        if group is None:
            group = {
                "chargeCategory": category,
                "chargeType": charge_type,
                "row_count": 0,
                "total_amount": 0.0,
                "total_quantity": 0.0,
                "missing_read_count": 0,
            }
            groups[key] = group
        group["row_count"] += 1
        group["total_amount"] += _number(row.get("amount"))
        group["total_quantity"] += _number(row.get("quantity"))
        group["missing_read_count"] += int(row.get("isMeterReadMissingOnDate") is True)
    return list(groups.values())


def _usage_summary(usage: dict[str, Any]) -> dict[str, Any]:
    """Copy consumption totals, intervals and register breakdowns."""
    summary = _fields(
        usage,
        "days",
        "total_usage",
        "latest_day",
        "latest_day_usage",
        "total_export",
        "latest_day_export",
        "total_controlled_load",
        "latest_day_controlled_load",
    )
    for name in ("daily", "export_daily", "controlled_load_daily"):
        summary[name] = [
            _fields(row, *_USAGE_DAY_FIELDS) for row in _rows(usage.get(name))
        ]
    intervals = usage.get("latest_intervals")
    summary["latest_intervals"] = (
        [
            item
            if type(item) is int or (isinstance(item, float) and isfinite(item))
            else None
            for item in intervals
        ]
        if isinstance(intervals, list)
        else []
    )
    summary["registers"] = [
        {
            **_fields(
                row,
                *_REGISTER_FIELDS,
                "key",
                "slug",
                "usage_class",
                "register_sensor",
                "days",
                "total",
                "latest_day",
                "latest_day_usage",
            ),
            "time_periods": [
                _fields(period, "start", "end")
                for period in _rows(row.get("time_periods"))
            ],
            "daily": [
                _fields(day, *_USAGE_DAY_FIELDS) for day in _rows(row.get("daily"))
            ],
        }
        for row in _rows(usage.get("registers"))
    ]
    return summary


def _labels(value: Any) -> list[str | None]:
    """Copy a list of portal labels under the same bounds as scalar fields."""
    return [_label(item) for item in value] if isinstance(value, list) else []


def _cost_summary(cost: dict[str, Any]) -> dict[str, Any]:
    """Copy daily costs, category totals and the projection."""
    summary = _fields(
        cost,
        "days",
        "total_amount",
        "total_quantity",
        "total_import_cost",
        "total_export_credit",
        "latest_day",
        "latest_day_amount",
        "latest_day_import_cost",
        "latest_day_export_credit",
        "latest_available_day",
        "latest_available_day_complete",
        "latest_day_zerohero_credit",
        "latest_day_zerohero_achieved",
    )
    for name in (
        "daily",
        "available_daily",
        "daily_totals",
        "daily_import_totals",
        "daily_export_credit_totals",
    ):
        summary[name] = [
            _fields(row, *_COST_DAY_FIELDS) for row in _rows(cost.get(name))
        ]
    summary["incomplete_days"] = _labels(cost.get("incomplete_days"))
    summary["projected_month"] = _fields(
        cost.get("projected_month"),
        "month",
        "cost_to_date",
        "projected_cost",
        "completed_days",
        "days_in_month",
        "latest_day",
    )
    summary["categories"] = [
        _fields(row, "chargeCategory", "amount", "quantity")
        for row in _rows(cost.get("categories"))
    ]
    return summary


def _service_diagnostics(service_ref: str, detail: dict[str, Any]) -> dict[str, Any]:
    """Project one service without returning meter identifiers or raw responses."""
    status = _mapping(detail.get("latest_data_status"))
    gas = _mapping(detail.get("gas_reading_summary"))
    weather = _mapping(detail.get("weather_summary"))
    return {
        "service_ref": service_ref,
        **_fields(detail.get("service"), "serviceType"),
        "has_meter": bool(_mapping(detail.get("meter"))),
        "latest_data_status": {
            **_fields(
                status,
                "status",
                "latest_ready_day",
                "latest_usage_day",
                "latest_cost_day",
                "latest_available_cost_day",
                "latest_available_cost_day_complete",
            ),
            "incomplete_cost_days": _labels(status.get("incomplete_cost_days")),
        },
        "usage_summary": _usage_summary(_mapping(detail.get("usage_summary"))),
        "usage_register_inventory": _usage_inventory(detail.get("usage")),
        "cost_summary": _cost_summary(_mapping(detail.get("cost_summary"))),
        "cost_category_inventory": _cost_inventory(detail.get("cost")),
        "gas_reading_summary": {
            **_fields(
                gas,
                "latest_reading",
                "latest_reading_date",
                "latest_reading_quality_method",
                "history_count",
                "history_truncated",
            ),
            "history": [
                _fields(row, "date", "read_index", "quality_method")
                for row in _rows(gas.get("history"))
            ],
        },
        "weather_summary": {
            **_fields(
                weather, "days", "latest_date", "latest_min_temp", "latest_max_temp"
            ),
            "daily": [
                _fields(row, "dateAsDate", "obMinTemp", "obMaxTemp")
                for row in _rows(weather.get("daily"))
            ],
        },
    }


def _diagnostics_data(data: Any) -> dict[str, Any] | None:
    """Build an allowlisted diagnostics snapshot without modifying live data."""
    if not isinstance(data, dict):
        return None
    accounts = _rows(data.get("accounts"))
    services = {service_id(row): row for row in _rows(data.get("services"))}
    details = {
        str(key): value for key, value in _mapping(data.get("service_data")).items()
    }
    service_refs = {
        key: f"service_{index}"
        for index, key in enumerate(dict.fromkeys((*services, *details)), start=1)
    }
    fetch_errors = _mapping(data.get("_fetch_errors"))
    result = {
        **_fields(data, "last_update", "last_failed_update"),
        "account_count": len(accounts),
        "service_count": len(service_refs),
        "services": [
            {"service_ref": ref, **_fields(services.get(key), "serviceType", "status")}
            for key, ref in service_refs.items()
        ],
        "service_data": {
            ref: _service_diagnostics(ref, _mapping(details[key]))
            for key, ref in service_refs.items()
            if key in details
        },
        "responses_present": {
            key: isinstance(data.get(key), dict) for key in _OPTIONAL_ENDPOINTS
        },
        "fetch_errors": {
            key: _REDACTED for key in _OPTIONAL_ENDPOINTS if key in fetch_errors
        },
        "global_summary": _fields(
            data.get("global_summary"),
            "refresh_status",
            "last_successful_refresh",
            "last_failed_refresh",
            "balance",
            "dashboard_balance",
            "latest_invoice_amount",
            "max_refundable_amount",
            "show_refundable_amount",
        ),
    }
    if data.get("refresh_error") is not None:
        result["refresh_error"] = _REDACTED
    return result


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return redacted diagnostics for a config entry."""
    coordinator = getattr(entry, "runtime_data", None) or hass.data.get(DOMAIN, {}).get(
        entry.entry_id
    )
    data = coordinator.data if coordinator else None

    config = dict(entry.data)
    if CONF_PASSWORD in config:
        config[CONF_PASSWORD] = "**REDACTED**"

    return {
        "entry": redact_sensitive(config),
        "data": _diagnostics_data(data),
    }
