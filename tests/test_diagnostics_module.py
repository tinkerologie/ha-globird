"""Tests for diagnostics payload redaction."""

from __future__ import annotations

import asyncio
import importlib
import json
import sys
import types
from copy import deepcopy
from pathlib import Path
from typing import Any

COMPONENT_PATH = Path(__file__).parents[1] / "custom_components"
INTEGRATION_PATH = COMPONENT_PATH / "globird"

custom_components = types.ModuleType("custom_components")
custom_components.__path__ = [str(COMPONENT_PATH)]  # type: ignore[attr-defined]
globird_package = types.ModuleType("custom_components.globird")
globird_package.__path__ = [str(INTEGRATION_PATH)]  # type: ignore[attr-defined]
sys.modules.setdefault("custom_components", custom_components)
sys.modules.setdefault("custom_components.globird", globird_package)

homeassistant = types.ModuleType("homeassistant")
config_entries = types.ModuleType("homeassistant.config_entries")
core = types.ModuleType("homeassistant.core")
util = types.ModuleType("homeassistant.util")
util_logging = types.ModuleType("homeassistant.util.logging")
config_entries.ConfigEntry = object
core.HomeAssistant = object
util_logging.log_exception = lambda *_args, **_kwargs: None
util.logging = util_logging
homeassistant.config_entries = config_entries
homeassistant.core = core
homeassistant.util = util
sys.modules.setdefault("homeassistant", homeassistant)
sys.modules.setdefault("homeassistant.config_entries", config_entries)
sys.modules.setdefault("homeassistant.core", core)
sys.modules.setdefault("homeassistant.util", util)
sys.modules.setdefault("homeassistant.util.logging", util_logging)

diagnostics = importlib.import_module("custom_components.globird.diagnostics")
client = importlib.import_module("custom_components.globird.client")


class FakeCoordinator:
    def __init__(self) -> None:
        self.data = {
            "accounts": [{"accountNumber": "123"}],
            "password": "hidden",
        }


class FakeHass:
    def __init__(self) -> None:
        self.data = {
            diagnostics.DOMAIN: {
                "entry-1": FakeCoordinator(),
            }
        }


class FakeEntry:
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self.entry_id = "entry-1"
        self.data = (
            data
            if data is not None
            else {
                "email": "user@example.test",
                "password": "secret",
            }
        )


def test_async_get_config_entry_diagnostics_redacts_sensitive_values() -> None:
    """Diagnostics should redact credentials and sensitive payload keys."""
    payload = asyncio.run(
        diagnostics.async_get_config_entry_diagnostics(FakeHass(), FakeEntry())
    )

    assert payload["entry"]["password"] == "**REDACTED**"
    assert payload["entry"]["email"] == "**REDACTED**"
    assert payload["data"]["account_count"] == 1
    assert "accounts" not in payload["data"]
    assert "password" not in payload["data"]


def test_async_get_config_entry_diagnostics_without_password_key() -> None:
    """Diagnostics should succeed when password key is absent from entry data."""
    payload = asyncio.run(
        diagnostics.async_get_config_entry_diagnostics(
            FakeHass(), FakeEntry(data={"email": "user@example.test"})
        )
    )
    assert payload["entry"]["email"] == "**REDACTED**"


def test_diagnostics_omits_portal_identifiers_in_values_and_keys() -> None:
    """Export only allowlisted fields, keeping the coordinator data intact."""
    canaries = {
        "accountId": "account-id-canary",
        "accountServiceId": "service-id-canary",
        "postCode": "postcode-canary",
        "siteIdentifier": "site-identifier-canary",
        "nmi": "nmi-canary",
        "serial": "serial-canary",
        "serialNumber": "serial-number-canary",
    }
    gas = {"siteIdentifier": canaries["siteIdentifier"], "serviceType": "Gas"}
    data = {
        "accounts": [{"accountId": canaries["accountId"]}],
        "services": [
            {**canaries, "serviceType": "Electricity", "status": "Active"},
            gas,
        ],
        "service_status": {
            "data": {"status-key-canary": "Active"},
            "message": "portal-message-canary",
        },
        "service_data": {
            canaries["accountServiceId"]: {
                "service": canaries,
                "meter": {"serialNumber": canaries["serialNumber"]},
                "usage": {
                    "data": [
                        {
                            "suffix": "E1",
                            "chargeType": "Private label 123456",
                            "unknownField": "unknown-field-canary",
                            "readDate": "2026-05-01",
                            "usage": 4.0,
                            "usageArray": ["interval-canary"],
                        }
                    ]
                },
                "weather_summary": {
                    "daily": [
                        {
                            "dateAsDate": "2026-05-01",
                            "obMinTemp": 17,
                            "distanceMeters": 98765,
                        }
                    ]
                },
            },
            canaries["siteIdentifier"]: {
                "service": gas,
                "gas_reading_summary": {
                    "latest_reading": 12,
                    "latest_reading_serial": "latest-serial-canary",
                    "history": [
                        {
                            "date": "2026-05-01",
                            "read_index": 12,
                            "serial": canaries["serial"],
                            "source": "source-canary",
                        }
                    ],
                },
            },
        },
        "_fetch_errors": {
            "dashboard": "fetch-error-canary",
            "unknown-key-canary": "failed",
        },
        "refresh_error": "refresh-error-canary",
        "global_summary": {
            "balance": 20.5,
            "dashboard": {
                "account_id": "derived-account-id-canary",
                "account_number": "derived-account-number-canary",
                "recent_transactions": [{"description": "transaction-canary"}],
                "latest_correspondence": {"message": "correspondence-canary"},
            },
        },
    }
    original = deepcopy(data)
    entry = FakeEntry()
    entry.runtime_data = types.SimpleNamespace(data=data)
    payload = asyncio.run(
        diagnostics.async_get_config_entry_diagnostics(FakeHass(), entry)
    )

    assert "canary" not in json.dumps(payload)
    assert "123456" not in json.dumps(payload)
    assert data == original
    projected = payload["data"]
    assert projected["services"] == [
        {"service_ref": "service_1", "serviceType": "Electricity", "status": "Active"},
        {"service_ref": "service_2", "serviceType": "Gas"},
    ]
    assert list(projected["service_data"]) == ["service_1", "service_2"]
    assert projected["service_data"]["service_1"]["has_meter"] is True
    assert projected["service_data"]["service_1"]["weather_summary"]["daily"] == [
        {"dateAsDate": "2026-05-01", "obMinTemp": 17}
    ]
    assert projected["service_data"]["service_2"]["gas_reading_summary"]["history"] == [
        {"date": "2026-05-01", "read_index": 12}
    ]
    assert projected["responses_present"]["service_status"] is True
    assert projected["fetch_errors"] == {"dashboard": "**REDACTED**"}
    assert projected["refresh_error"] == "**REDACTED**"
    assert projected["global_summary"] == {"balance": 20.5}


def test_diagnostics_retains_controlled_load_and_cost_evidence() -> None:
    """Inventories distinguish category rows that share a display register."""
    usage = {
        "data": [
            {
                "readDate": day,
                "suffix": suffix,
                "chargeType": charge_type,
                "chargeCategoryCode": category,
                "usage": amount,
                "usageArray": [amount],
                "timePeriods": [{"startTime": "00:00", "endTime": "05:00"}],
            }
            for day in ("2026-05-01", "2026-05-02")
            for suffix, charge_type, category, amount in (
                ("E1", "Peak Usage", "USAGE", 5.0),
                ("E2", "Controlled Load 1", "CONTROL", 2.0),
                ("E3", "Controlled Load 2", "control", 1.25),
                ("B1", "Solar Export", "SOLAR", 1.5),
            )
        ]
    }
    usage["data"].append(
        {**usage["data"][1], "chargeCategoryCode": "USAGE", "usage": 1.0}
    )
    cost = {
        "data": [
            {
                "date": "2026/05/01",
                "chargeCategory": "USAGE",
                "amount": 1.2,
                "quantity": 3,
            },
            {
                "date": "2026/05/01",
                "chargeCategory": "SOLAR",
                "amount": -0.5,
                "quantity": 2,
            },
            {
                "date": "2026/05/02",
                "chargeCategory": "SUPPLY",
                "amount": 0.8,
                "quantity": 0,
                "isMeterReadMissingOnDate": True,
            },
        ]
    }
    data = {
        "service_data": {
            "opaque-service-id": {
                "usage": usage,
                "usage_summary": client.build_usage_summary(usage),
                "cost": cost,
                "cost_summary": client.build_cost_summary(cost),
            }
        }
    }
    service = diagnostics._diagnostics_data(data)["service_data"]["service_1"]

    usage_summary = service["usage_summary"]
    assert usage_summary["total_controlled_load"] == 6.5
    assert [day["usage"] for day in usage_summary["controlled_load_daily"]] == [
        3.25,
        3.25,
    ]
    controlled_registers = [
        row
        for row in usage_summary["registers"]
        if row["usage_class"] == "controlled_load"
    ]
    assert {row["chargeCategoryCode"] for row in controlled_registers} == {
        "CONTROL",
        "control",
    }
    assert controlled_registers[0]["time_periods"] == [
        {"start": "00:00", "end": "05:00"}
    ]
    inventory = {
        row["chargeCategoryCode"]: row
        for row in service["usage_register_inventory"]
        if row["suffix"] == "E2"
    }
    assert inventory["USAGE"]["row_count"] == 1
    assert inventory["USAGE"]["usage_class"] == "general_import"
    assert inventory["CONTROL"]["row_count"] == 2
    assert inventory["CONTROL"]["total_usage"] == 4.0
    assert inventory["CONTROL"]["first_read_date"] == "2026-05-01"
    assert inventory["CONTROL"]["last_read_date"] == "2026-05-02"
    assert inventory["CONTROL"]["interval_counts"] == [1]
    assert service["cost_summary"]["incomplete_days"] == ["2026/05/02"]
    assert {row["chargeCategory"] for row in service["cost_summary"]["categories"]} == {
        "USAGE",
        "SOLAR",
    }
    costs = {row["chargeCategory"]: row for row in service["cost_category_inventory"]}
    assert costs["SUPPLY"]["missing_read_count"] == 1
    assert costs["SUPPLY"]["total_amount"] == 0.8
    assert costs["USAGE"]["total_quantity"] == 3


def test_diagnostics_handles_partial_cache_and_missing_coordinator() -> None:
    """A stale response or an unloaded entry still returns a safe payload."""
    result = asyncio.run(
        diagnostics.async_get_config_entry_diagnostics(
            types.SimpleNamespace(data={}), FakeEntry()
        )
    )
    assert result["data"] is None

    partial = diagnostics._diagnostics_data(
        {
            "services": "malformed",
            "service_data": {"partial": None},
            "last_failed_update": 100.0,
            "refresh_error": "unstructured provider error",
        }
    )
    assert partial["last_failed_update"] == 100.0
    assert partial["refresh_error"] == "**REDACTED**"
    assert partial["service_data"]["service_1"]["usage_register_inventory"] == []


def test_diagnostics_keeps_inventory_when_cached_values_are_malformed() -> None:
    """Malformed measurements contribute no value and cannot leak free text."""
    diagnostics_data = diagnostics._diagnostics_data(
        {
            "last_update": "private timestamp",
            "service_data": {
                "private service": {
                    "usage": {
                        "data": [
                            {
                                "suffix": "E2",
                                "chargeType": "Controlled Load",
                                "usage": True,
                            },
                            {
                                "suffix": "E2",
                                "chargeType": "Controlled Load",
                                "usage": "private usage",
                            },
                        ]
                    },
                    "cost": {
                        "data": [
                            {
                                "chargeCategory": "USAGE",
                                "amount": float("inf"),
                                "quantity": 1,
                            },
                            {
                                "chargeCategory": "USAGE",
                                "amount": "1.25",
                                "quantity": 2,
                            },
                        ]
                    },
                }
            },
        }
    )
    assert "private" not in json.dumps(diagnostics_data)
    service = diagnostics_data["service_data"]["service_1"]
    assert service["usage_register_inventory"][0]["total_usage"] == 0.0
    assert service["usage_register_inventory"][0]["first_read_date"] is None
    assert service["cost_category_inventory"][0]["row_count"] == 2
    assert service["cost_category_inventory"][0]["total_amount"] == 1.25
    assert service["cost_category_inventory"][0]["total_quantity"] == 3.0
