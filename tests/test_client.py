"""Tests for the GloBird API helpers."""

from __future__ import annotations

import asyncio
import calendar
import importlib
import json
import sys
import types
import unittest
from datetime import date, timedelta
from pathlib import Path
from typing import Any

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "globird_responses.json"
ZEROHERO_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "globird_zerohero_tou_responses.json"
)
GAS_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "globird_gas_responses.json"
COMPONENT_PATH = Path(__file__).parents[1] / "custom_components"
INTEGRATION_PATH = COMPONENT_PATH / "globird"

custom_components = types.ModuleType("custom_components")
custom_components.__path__ = [str(COMPONENT_PATH)]  # type: ignore[attr-defined]
globird_package = types.ModuleType("custom_components.globird")
globird_package.__path__ = [str(INTEGRATION_PATH)]  # type: ignore[attr-defined]
sys.modules.setdefault("custom_components", custom_components)
sys.modules.setdefault("custom_components.globird", globird_package)

api = importlib.import_module("custom_components.globird.client")
api_impl = importlib.import_module("custom_components.globird.api.client")
importlib.import_module("custom_components.globird.api")

GloBirdCaptchaRequired = api.GloBirdCaptchaRequired
GloBirdAuthError = api.GloBirdAuthError
GloBirdClient = api.GloBirdClient
build_cost_summary = api.build_cost_summary
build_billing_period_projection = api.build_billing_period_projection
build_gas_reading_summary = api.build_gas_reading_summary
build_latest_data_status = api.build_latest_data_status
build_usage_summary = api.build_usage_summary
build_weather_summary = api.build_weather_summary
all_services_ready_for_day = api.all_services_ready_for_day
cost_attributes = api.cost_attributes
extract_accounts_and_services = api.extract_accounts_and_services
redact_sensitive = api.redact_sensitive
select_meter_for_service = api.select_meter_for_service
usage_attributes = api.usage_attributes


def load_fixtures() -> dict[str, Any]:
    """Load sanitized fixture payloads."""
    return json.loads(FIXTURE_PATH.read_text())


def load_gas_fixtures() -> dict[str, Any]:
    """Load dedicated gas fixture payloads."""
    return json.loads(GAS_FIXTURE_PATH.read_text())


def load_zerohero_fixtures() -> dict[str, Any]:
    """Load redacted live ZEROHERO time-of-use payloads (three days)."""
    return json.loads(ZEROHERO_FIXTURE_PATH.read_text())


class FakeResponse:
    """Minimal aiohttp response context manager."""

    def __init__(self, status: int, payload: dict[str, Any]) -> None:
        self.status = status
        self._payload = payload

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None

    async def text(self) -> str:
        return json.dumps(self._payload)


class FakeSession:
    """Minimal aiohttp session for deterministic request sequences."""

    closed = False
    cookie_jar: list[Any] = []

    def __init__(self, responses: list[tuple[int, dict[str, Any]]]) -> None:
        self._responses = list(responses)
        self.requests: list[tuple[str, str, dict[str, Any]]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        self.requests.append((method, url, kwargs))
        if not self._responses:
            raise AssertionError(f"Unexpected request: {method} {url}")
        status, payload = self._responses.pop(0)
        return FakeResponse(status, payload)


def stub_password_encryption(client: Any) -> None:
    """Keep auth tests focused on request flow, not RSA encryption."""

    async def fake_encrypt_password(password: str) -> str:
        return password

    client._encrypt_password = fake_encrypt_password


def test_authenticate_success() -> None:
    """Login posts credentials and validates with currentuser."""
    fixtures = load_fixtures()
    session = FakeSession(
        [
            (200, fixtures["login_success"]),
            (200, fixtures["current_user"]),
        ]
    )
    client = GloBirdClient(session=session, base_url="https://example.test")
    stub_password_encryption(client)

    result = asyncio.run(
        client.authenticate("user@example.test", "secret", fresh_session=False)
    )

    assert client.is_authenticated is True
    assert result["data"]["emailAddress"] == "user@example.test"
    assert session.requests[0][0] == "POST"
    assert session.requests[0][1].endswith("/api/account/login")
    assert session.requests[0][2]["json"] == {
        "emailAddress": "user@example.test",
        "password": "secret",
        "rememberMe": False,
    }
    assert session.requests[1][1].endswith("/api/account/currentuser")


def test_authenticate_captcha_required() -> None:
    """Captcha flags produce a dedicated auth error."""
    fixtures = load_fixtures()
    session = FakeSession([(200, fixtures["login_captcha"])])
    client = GloBirdClient(session=session, base_url="https://example.test")
    stub_password_encryption(client)

    try:
        asyncio.run(
            client.authenticate("user@example.test", "secret", fresh_session=False)
        )
    except GloBirdCaptchaRequired:
        pass
    else:
        raise AssertionError("Expected captcha-required authentication failure")

    assert client.is_authenticated is False


def test_authenticate_invalid_credentials() -> None:
    """Failed login payloads produce a dedicated auth error."""
    fixtures = load_fixtures()
    session = FakeSession([(200, fixtures["login_failure"])])
    client = GloBirdClient(session=session, base_url="https://example.test")
    stub_password_encryption(client)

    try:
        asyncio.run(
            client.authenticate("user@example.test", "wrong", fresh_session=False)
        )
    except GloBirdAuthError:
        pass
    else:
        raise AssertionError("Expected invalid-auth failure")

    assert client.is_authenticated is False


def test_session_expiry_reauthenticates_once() -> None:
    """A 401 response triggers exactly one credential re-login and retry."""
    fixtures = load_fixtures()
    session = FakeSession(
        [
            (200, fixtures["login_success"]),
            (200, fixtures["current_user"]),
            (401, {"success": True}),
            (200, fixtures["login_success"]),
            (200, fixtures["current_user"]),
            (200, fixtures["balance"]),
        ]
    )
    client = GloBirdClient(session=session, base_url="https://example.test")
    stub_password_encryption(client)

    async def scenario() -> dict[str, Any]:
        await client.authenticate("user@example.test", "secret", fresh_session=False)
        return await client.get_balance()

    result = asyncio.run(scenario())

    assert result["data"]["balance"] == 123.45
    requested_paths = [
        request[1].replace("https://example.test", "") for request in session.requests
    ]
    assert requested_paths == [
        "/api/account/login",
        "/api/account/currentuser",
        "/api/transaction/balance",
        "/api/account/login",
        "/api/account/currentuser",
        "/api/transaction/balance",
    ]


def test_get_usage_uses_basic_meter_endpoint_for_non_smart_meter() -> None:
    """Gas/basic services should use /api/site/basicmeterread."""
    session = FakeSession([(200, {"data": {}, "success": True})])
    client = GloBirdClient(session=session, base_url="https://example.test")
    account_service_id = 123456

    asyncio.run(
        client.get_usage(
            identifier="TEST-MIRN-001",
            serial_number="TEST-METER-001",
            account_service_id=account_service_id,
            is_smart=False,
            days=31,
        )
    )

    assert session.requests[0][0] == "POST"
    assert session.requests[0][1].endswith(
        f"/api/site/basicmeterread?accountServiceId={account_service_id}"
    )


def test_extract_accounts_services_and_summaries() -> None:
    """Parser helpers produce compact, recorder-safe summaries."""
    fixtures = load_fixtures()

    accounts, services = extract_accounts_and_services(fixtures["current_user"])
    usage = build_usage_summary(fixtures["usage"])
    cost = build_cost_summary(fixtures["cost"])
    weather = build_weather_summary(fixtures["weather"])

    assert len(accounts) == 2
    assert len(services) == 2
    assert usage["total_usage"] == 3.5
    assert usage["latest_day"] == "2026-04-02"
    assert usage["latest_intervals"] == [0.4, 0.5, 0.6]
    # Fixture: 2 days x (SOLAR + USAGE + SUPPLY). Net = (1.48) + (-0.43) = 1.05
    assert cost["total_amount"] == 1.05
    assert cost["total_quantity"] == 21.5
    # latest_day_amount is the net sum for 2026/04/02: -2.36 + 0.60 + 1.33 = -0.43
    assert cost["latest_day_amount"] == -0.43
    assert cost["latest_available_day"] == "2026/04/02"
    assert cost["latest_available_day_complete"] is True
    assert weather["latest_max_temp"] == 29


def test_extract_accounts_and_services_includes_active_gas_services() -> None:
    """Mixed accounts should retain active gas services."""
    payload = {
        "data": {
            "accounts": [
                {
                    "accountId": 1,
                    "accountNumber": "A001",
                    "accountAddress": "Address",
                    "services": [
                        {
                            "accountServiceId": 10,
                            "serviceType": "Power",
                            "status": "Switched",
                        },
                        {
                            "accountServiceId": 11,
                            "serviceType": "Gas",
                            "status": "Switched",
                        },
                        {
                            "accountServiceId": 12,
                            "serviceType": "Gas",
                            "status": "Closed",
                        },
                        {
                            "accountServiceId": 13,
                            "serviceType": "Internet",
                            "status": "Switched",
                        },
                    ],
                }
            ]
        }
    }

    _, services = extract_accounts_and_services(payload)

    assert [service["accountServiceId"] for service in services] == [10, 11]


def test_select_meter_rejects_another_services_identified_meter() -> None:
    """A scoped response for another service must not be used as a fallback."""
    selected = select_meter_for_service(
        {"siteIdentifier": "MIRN-GAS"},
        {
            "data": [
                {
                    "siteIdentifier": "NMI-POWER",
                    "meterReadType": "SMART",
                    "serialNumber": "power-meter",
                    "serialStatus": "Active",
                }
            ]
        },
    )

    assert selected is None


def test_build_gas_reading_summary_tracks_latest_reading_and_history() -> None:
    """Gas summaries should expose the latest read index and recorder-safe history."""
    payload = load_gas_fixtures()["gas_reading_summary_payload"]

    summary = build_gas_reading_summary(payload)

    assert summary["latest_reading"] == 3050.0
    assert summary["latest_reading_date"] == "2026-07-12"
    assert summary["latest_reading_source"] == "Invoice Read Data"
    assert summary["latest_reading_serial"] == "TEST-METER-001"
    assert summary["history_count"] == 3
    assert summary["history_recent"][-1]["read_index"] == 3050.0


def test_select_meter_prefers_energized_smart_over_removed_basic() -> None:
    """Meter upgrades should use the current smart meter, not the removed basic meter."""
    selected = select_meter_for_service(
        {"siteIdentifier": "NMI123"},
        {
            "data": [
                {
                    "siteIdentifier": "NMI123",
                    "meterReadType": "BASIC",
                    "serialNumber": "old-meter",
                    "serialStatus": "Removed",
                },
                {
                    "siteIdentifier": "NMI123",
                    "meterReadType": "SMART",
                    "serialNumber": "new-meter",
                    "serialStatus": "Energized",
                },
            ],
        },
    )

    assert selected is not None
    assert selected["serialNumber"] == "new-meter"
    assert selected["meterReadType"] == "SMART"


def test_select_meter_preserves_order_for_equivalent_meters() -> None:
    """Equivalent active meters keep the portal's first returned row."""
    selected = select_meter_for_service(
        {},
        {
            "data": [
                {
                    "meterReadType": "BASIC",
                    "serialNumber": "first",
                    "serialStatus": "Active",
                },
                {
                    "meterReadType": "BASIC",
                    "serialNumber": "second",
                    "serialStatus": "Active",
                },
            ],
        },
    )

    assert selected is not None
    assert selected["serialNumber"] == "first"


def test_cost_summary_net_daily_is_sum_not_last_row() -> None:
    """latest_day_amount sums all rows for the day — not just the last row (SUPPLY charge)."""
    payload = {
        "data": [
            {
                "chargeCategory": "SOLAR",
                "chargeType": None,
                "date": "2026/04/24",
                "amount": -3.12,
                "quantity": 21.0,
            },
            {
                "chargeCategory": "USAGE",
                "chargeType": None,
                "date": "2026/04/24",
                "amount": 0.21,
                "quantity": 47.0,
            },
            {
                "chargeCategory": "SUPPLY",
                "chargeType": None,
                "date": "2026/04/24",
                "amount": 1.40,
                "quantity": 0.0,
            },
        ],
        "message": None,
        "success": True,
    }
    cost = build_cost_summary(payload)
    # Net = -3.12 + 0.21 + 1.40 = -1.51 — NOT the supply-charge-only value of 1.40
    assert cost["total_amount"] == -1.51
    assert cost["latest_day"] == "2026/04/24"
    assert cost["latest_day_amount"] == -1.51
    assert cost["latest_available_day_complete"] is True


def test_cost_summary_ignores_supply_only_partial_latest_day() -> None:
    """latest_day ignores a newer supply-only day until usage/export rows arrive."""
    payload = {
        "data": [
            {
                "chargeCategory": "SOLAR",
                "chargeType": None,
                "date": "2026/05/15",
                "amount": -2.10,
                "quantity": 14.0,
            },
            {
                "chargeCategory": "USAGE",
                "chargeType": None,
                "date": "2026/05/15",
                "amount": 0.40,
                "quantity": 3.0,
            },
            {
                "chargeCategory": "SUPPLY",
                "chargeType": None,
                "date": "2026/05/15",
                "amount": 1.24,
                "quantity": 0.0,
            },
            {
                "chargeCategory": "SUPPLY",
                "chargeType": None,
                "date": "2026/05/16",
                "amount": 1.24,
                "quantity": 0.0,
            },
        ],
        "message": None,
        "success": True,
    }

    cost = build_cost_summary(payload)

    assert cost["latest_available_day"] == "2026/05/16"
    assert cost["latest_available_day_complete"] is False
    assert cost["latest_day"] == "2026/05/15"
    assert cost["latest_day_amount"] == -0.46
    assert cost["total_amount"] == -0.46
    assert cost["incomplete_days"] == ["2026/05/16"]
    assert cost["daily"] == [
        row for row in cost["available_daily"] if row["date"] == "2026/05/15"
    ]


def test_latest_data_status_waits_for_cost_to_match_usage() -> None:
    """Latest Data Date should not advance while cost lags usage."""
    usage = {"latest_day": "2026-06-01"}
    cost = {
        "latest_day": "2026/05/31",
        "latest_available_day": "2026/06/01",
        "latest_available_day_complete": False,
        "incomplete_days": ["2026/06/01"],
    }

    status = build_latest_data_status(usage, cost)

    assert status["status"] == "waiting_for_cost"
    assert status["latest_ready_day"] == "2026/05/31"
    assert status["latest_usage_day"] == "2026-06-01"
    assert status["latest_cost_day"] == "2026/05/31"
    assert status["latest_available_cost_day"] == "2026/06/01"
    assert status["incomplete_cost_days"] == ["2026/06/01"]


def test_latest_data_status_ready_when_usage_and_cost_align() -> None:
    """Latest data is ready once usage and complete cost dates agree."""
    usage = {"latest_day": "2026-06-01"}
    cost = {
        "latest_day": "2026/06/01",
        "latest_available_day": "2026/06/01",
        "latest_available_day_complete": True,
        "incomplete_days": [],
    }

    status = build_latest_data_status(usage, cost)

    assert status["status"] == "ready"
    assert status["latest_ready_day"] == "2026/06/01"


def test_all_services_ready_for_day_requires_every_service_ready() -> None:
    """Polling can slow only once every discovered service is ready."""
    service_data = {
        "svc-1": {
            "latest_data_status": {
                "status": "ready",
                "latest_ready_day": "2026/06/01",
            },
        },
        "svc-2": {
            "latest_data_status": {
                "status": "waiting_for_cost",
                "latest_ready_day": "2026/05/31",
            },
        },
    }

    assert all_services_ready_for_day(service_data, date(2026, 6, 1)) is False

    service_data["svc-2"]["latest_data_status"] = {
        "status": "ready",
        "latest_ready_day": "2026-06-01",
    }

    assert all_services_ready_for_day(service_data, date(2026, 6, 1)) is True


def test_all_services_ready_for_day_rejects_stale_ready_data() -> None:
    """Aligned old data should not pause polling for the current daily target."""
    service_data = {
        "svc-1": {
            "latest_data_status": {
                "status": "ready",
                "latest_ready_day": "2026/05/31",
            },
        },
    }

    assert all_services_ready_for_day(service_data, date(2026, 6, 1)) is False


def test_usage_summary_tracks_all_registers_and_b_exports() -> None:
    """Usage summaries expose all returned registers and treat B* suffixes as export."""
    payload = {
        "data": [
            {
                "readDate": "2026-04-24",
                "usage": 3.0,
                "suffix": "E1",
                "chargeType": "Peak",
                "chargeCategoryCode": "USAGE",
                "usageArray": [1.0, 2.0],
            },
            {
                "readDate": "2026-04-24",
                "usage": 1.0,
                "suffix": "E2",
                "chargeType": "Controlled Load",
                "chargeCategoryCode": "CONTROL",
                "usageArray": [0.25, 0.75],
            },
            {
                "readDate": "2026-04-24",
                "usage": 2.5,
                "suffix": "B2",
                "chargeType": "Super Export",
                "chargeCategoryCode": "SOLAR",
                "usageArray": [1.5, 1.0],
            },
            {
                "readDate": "2026-04-24",
                "usage": 0.9,
                "suffix": "E3",
                "chargeType": "Solar Export",
                "chargeCategoryCode": "SOLAR",
                "usageArray": [0.4, 0.5],
            },
        ],
        "message": None,
        "success": True,
    }

    usage = build_usage_summary(payload)

    # E2 / CONTROL is controlled load: kept out of general import (#19).
    assert usage["total_usage"] == 3.0
    assert usage["latest_day_usage"] == 3.0
    assert usage["total_controlled_load"] == 1.0
    assert usage["latest_day_controlled_load"] == 1.0
    assert usage["total_export"] == 3.4
    assert usage["latest_day_export"] == 3.4
    assert [register["key"] for register in usage["registers"]] == [
        "B2-Super Export",
        "E1-Peak",
        "E2-Controlled Load",
        "E3-Solar Export",
    ]
    assert usage["registers"][0]["direction"] == "export"
    assert usage["registers"][2]["chargeCategoryCode"] == "CONTROL"
    assert usage["registers"][2]["usage_class"] == "controlled_load"
    assert usage["registers"][3]["direction"] == "export"


def test_usage_summary_keeps_solar_soak_import_register_out_of_export() -> None:
    """Solar-named shoulder rates are import usage, not feed-in energy."""
    payload = {
        "data": [
            {
                "readDate": "2026-09-07",
                "usage": 4.2,
                "suffix": "E1",
                "chargeType": "Solar Soak",
                "chargeCategoryCode": "SOLAR",
                "usageArray": [2.1, 2.1],
            },
            {
                "readDate": "2026-09-07",
                "usage": 1.5,
                "suffix": "B1",
                "chargeType": "Solar Export",
                "chargeCategoryCode": "SOLAR",
                "usageArray": [0.5, 1.0],
            },
        ],
        "message": None,
        "success": True,
    }

    usage = build_usage_summary(payload)

    assert usage["total_usage"] == 4.2
    assert usage["latest_day_usage"] == 4.2
    assert usage["total_export"] == 1.5
    assert usage["latest_day_export"] == 1.5
    assert [register["direction"] for register in usage["registers"]] == [
        "export",
        "import",
    ]


def _registers_by_key(usage: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return usage summary registers keyed by their portal key."""
    return {register["key"]: register for register in usage["registers"]}


def test_usage_summary_excludes_zerohero_reward_registers_live_shape() -> None:
    """ZeroHero and Super Export top up rows are subsets, not extra energy (#17)."""
    usage = build_usage_summary(load_zerohero_fixtures()["electricity_usage"])

    # Only the USAGE / SOLAR rows count; they match the portal cost quantities.
    assert usage["total_usage"] == 0.929
    assert usage["latest_day"] == "2026/10/16"
    assert usage["latest_day_usage"] == 0.19
    assert [row["usage"] for row in usage["daily"]] == [0.489, 0.25, 0.19]
    assert usage["total_export"] == 48.173
    assert usage["latest_day_export"] == 22.43
    assert [row["usage"] for row in usage["export_daily"]] == [14.718, 11.025, 22.43]
    assert usage["total_controlled_load"] is None
    assert usage["controlled_load_daily"] == []

    registers = _registers_by_key(usage)
    zerohero = registers["E1-ZeroHero"]
    assert zerohero["usage_class"] == "tracking"
    assert zerohero["direction"] == "import"
    assert zerohero["chargeCategoryCode"] == "LOW_USAGE_REWARD_PER_DAY"
    assert zerohero["total"] == 0.241
    assert zerohero["register_sensor"] is False
    top_up = registers["B1-Super Export top up"]
    assert top_up["usage_class"] == "tracking"
    assert top_up["direction"] == "export"
    assert top_up["total"] == 0.095
    assert registers["E1-Peak Usage"]["usage_class"] == "general_import"
    assert registers["B1-Solar/Generation Feed in (4pm-11pm)"]["usage_class"] == (
        "export"
    )


def test_usage_summary_latest_intervals_count_each_meter_channel_once() -> None:
    """Every row repeats its register's full-day usageArray; sum it once."""
    usage = build_usage_summary(load_zerohero_fixtures()["electricity_usage"])

    assert len(usage["latest_intervals"]) == 288
    assert round(sum(usage["latest_intervals"]), 3) == usage["latest_day_usage"]


def test_usage_summary_sums_intervals_that_differ_per_row() -> None:
    """Per-period interval arrays (older payloads) are still summed element-wise."""
    usage = build_usage_summary(
        {
            "data": [
                {
                    "readDate": "2026-04-24",
                    "usage": 1.0,
                    "suffix": "E1",
                    "chargeType": "Peak",
                    "chargeCategoryCode": "USAGE",
                    "usageArray": [1.0, 0.0],
                },
                {
                    "readDate": "2026-04-24",
                    "usage": 2.0,
                    "suffix": "E1",
                    "chargeType": "Offpeak",
                    "chargeCategoryCode": "USAGE",
                    "usageArray": [0.0, 2.0],
                },
            ]
        }
    )

    assert usage["latest_intervals"] == [1.0, 2.0]

    # A longer array from another channel keeps its extra intervals.
    longer = build_usage_summary(
        {
            "data": [
                {
                    "readDate": "2026-04-24",
                    "usage": 1.0,
                    "suffix": "E1",
                    "chargeCategoryCode": "USAGE",
                    "usageArray": [1.0],
                },
                {
                    "readDate": "2026-04-24",
                    "usage": 1.0,
                    "suffix": "E2",
                    "chargeCategoryCode": "USAGE",
                    "usageArray": [0.5, 9.0],
                },
            ]
        }
    )
    assert longer["latest_intervals"] == [1.5, 9.0]


def test_cost_usage_quantities_match_energy_registers_live_shape() -> None:
    """The portal bills only the energy registers, confirming the #17 split."""
    fixtures = load_zerohero_fixtures()
    usage = build_usage_summary(fixtures["electricity_usage"])
    cost = build_cost_summary(fixtures["electricity_cost"])
    quantities = {row["chargeCategory"]: row["quantity"] for row in cost["categories"]}

    # Cost quantities are rounded to 0.01 kWh per day, so allow 0.01 per day.
    assert abs(quantities["USAGE"] - usage["total_usage"]) <= 0.03
    assert abs(quantities["SOLAR"] - usage["total_export"]) <= 0.03
    # Adding the tracking rows would overshoot the billed quantities.
    assert usage["total_usage"] + 0.241 - quantities["USAGE"] > 0.2
    assert cost["total_export_credit"] == 0.02
    assert cost["latest_day_zerohero_credit"] == -1.0


def test_usage_registers_expose_time_periods_daily_and_sensor_flag() -> None:
    """Energy registers carry what per-register sensors and statistics need (#18)."""
    usage = build_usage_summary(load_zerohero_fixtures()["electricity_usage"])
    registers = _registers_by_key(usage)

    offpeak = registers["E1-Offpeak Usage"]
    assert offpeak["slug"] == "e1_offpeak_usage"
    assert offpeak["time_periods"] == [{"start": "12:00", "end": "15:00"}]
    assert offpeak["register_sensor"] is True
    assert [row["readDate"] for row in offpeak["daily"]] == [
        "2026/10/14",
        "2026/10/15",
        "2026/10/16",
    ]
    assert registers["E1-Shoulder Usage"]["time_periods"] == [
        {"start": "00:00", "end": "12:00"},
        {"start": "15:00", "end": "16:00"},
        {"start": "23:00", "end": "24:00"},
    ]
    feed_in = registers["B1-Solar/Generation Feed in (4pm-11pm)"]
    assert feed_in["slug"] == "b1_solar_generation_feed_in_4pm_11pm"
    assert feed_in["register_sensor"] is True
    assert sorted(
        register["slug"]
        for register in usage["registers"]
        if register["register_sensor"]
    ) == [
        "b1_solar_generation_feed_in_11pm_4pm",
        "b1_solar_generation_feed_in_4pm_11pm",
        "e1_offpeak_usage",
        "e1_peak_usage",
        "e1_shoulder_usage",
    ]


def test_usage_attributes_list_export_registers_for_export_sensors() -> None:
    """Export sensors list B1 registers, including the add-on tracking row."""
    usage = build_usage_summary(load_zerohero_fixtures()["electricity_usage"])

    export_attrs = usage_attributes(usage, direction="export")
    import_attrs = usage_attributes(usage, direction="import")

    assert [register["key"] for register in export_attrs["registers"]] == [
        "B1-Solar/Generation Feed in (11pm-4pm)",
        "B1-Solar/Generation Feed in (4pm-11pm)",
        "B1-Super Export top up",
    ]
    assert export_attrs["registers"][2]["usage_class"] == "tracking"
    assert export_attrs["daily_count"] == 3
    assert [register["key"] for register in import_attrs["registers"]] == [
        "E1-Offpeak Usage",
        "E1-Peak Usage",
        "E1-Shoulder Usage",
        "E1-ZeroHero",
    ]


def test_flat_rate_registers_get_no_register_sensor() -> None:
    """A single register per class is already the class total: no extra sensor."""
    usage = build_usage_summary(load_fixtures()["usage"])

    assert usage["registers"]
    assert not any(register["register_sensor"] for register in usage["registers"])


def test_usage_classification_edge_cases() -> None:
    """Category matching, missing categories and unknown categories (#17, #19)."""
    rows = [
        # Missing category: legacy rows keep counting.
        {"readDate": "2026-05-01", "usage": 1.0, "suffix": "E1", "chargeType": "A"},
        # Case and whitespace are ignored.
        {
            "readDate": "2026-05-01",
            "usage": 2.0,
            "suffix": "E1",
            "chargeType": "B",
            "chargeCategoryCode": " usage ",
        },
        # CLIMATE is an energy category the portal totals as import.
        {
            "readDate": "2026-05-01",
            "usage": 0.5,
            "suffix": "E1",
            "chargeType": "C",
            "chargeCategoryCode": "Climate",
        },
        # Unknown non-energy category: tracking only.
        {
            "readDate": "2026-05-01",
            "usage": 9.0,
            "suffix": "E1",
            "chargeType": "Bonus",
            "chargeCategoryCode": "SOME_NEW_REWARD",
        },
        # Unknown import register on another suffix stays general import.
        {
            "readDate": "2026-05-01",
            "usage": 4.0,
            "suffix": "E2",
            "chargeType": "Usage",
            "chargeCategoryCode": "USAGE",
        },
        "not-a-row",
    ]

    usage = build_usage_summary({"data": rows})
    registers = _registers_by_key(usage)

    assert usage["total_usage"] == 7.5
    assert usage["total_controlled_load"] is None
    assert registers["E1-Bonus"]["usage_class"] == "tracking"
    assert registers["E1-Bonus"]["register_sensor"] is False
    assert registers["E2-Usage"]["usage_class"] == "general_import"
    assert registers["E2-Usage"]["register_sensor"] is True
    assert registers["E1-A"]["time_periods"] == []


def test_usage_summary_with_only_tracking_rows_keeps_registers() -> None:
    """Totals are empty when no energy row exists, but the registers stay visible."""
    usage = build_usage_summary(
        {
            "data": [
                {
                    "readDate": "2026-05-01",
                    "usage": 1.5,
                    "suffix": "E1",
                    "chargeType": "ZeroHero",
                    "chargeCategoryCode": "LOW_USAGE_REWARD_PER_DAY",
                    "timePeriods": [
                        {"startTime": "18:00:00", "endTime": "21:00:00"},
                        {"startTime": "18:00:00", "endTime": "21:00:00"},
                        {"startTime": None, "endTime": "bad"},
                        "not-a-period",
                    ],
                }
            ]
        }
    )

    assert usage["days"] == 0
    assert usage["total_usage"] is None
    assert usage["daily"] == []
    assert usage["total_export"] is None
    assert [register["key"] for register in usage["registers"]] == ["E1-ZeroHero"]
    assert usage["registers"][0]["time_periods"] == [
        {"start": "18:00", "end": "21:00"},
        {"start": None, "end": "bad"},
    ]


def test_controlled_load_registers_are_split_from_general_import() -> None:
    """CONTROL rows get their own totals and per-register flags (#19)."""
    rows = [
        {
            "readDate": day,
            "usage": usage,
            "suffix": suffix,
            "chargeType": charge_type,
            "chargeCategoryCode": category,
        }
        for day in ("2026-05-01", "2026-05-02")
        for suffix, charge_type, category, usage in (
            ("E1", "Peak Usage", "USAGE", 5.0),
            ("E2", "Controlled Load 1", "CONTROL", 2.0),
            ("E3", "Controlled Load 2", "control", 1.25),
        )
    ]

    usage = build_usage_summary({"data": rows})
    registers = _registers_by_key(usage)

    assert usage["total_usage"] == 10.0
    assert usage["total_controlled_load"] == 6.5
    assert usage["latest_day_controlled_load"] == 3.25
    assert [row["usage"] for row in usage["controlled_load_daily"]] == [3.25, 3.25]
    assert registers["E1-Peak Usage"]["register_sensor"] is False
    assert registers["E2-Controlled Load 1"]["register_sensor"] is True
    assert registers["E3-Controlled Load 2"]["usage_class"] == "controlled_load"

    attrs = usage_attributes(usage, direction="controlled_load")
    assert attrs["daily_count"] == 2
    assert [register["key"] for register in attrs["registers"]] == [
        "E2-Controlled Load 1",
        "E3-Controlled Load 2",
    ]
    assert attrs["registers"][0]["usage_class"] == "controlled_load"
    import_attrs = usage_attributes(usage, direction="import")
    assert [register["key"] for register in import_attrs["registers"]] == [
        "E1-Peak Usage"
    ]


def test_register_slugs_stay_unique() -> None:
    """Two portal keys that normalise to the same slug get distinct slugs."""
    usage = build_usage_summary(
        {
            "data": [
                {
                    "readDate": "2026-05-01",
                    "usage": 1.0,
                    "suffix": "E1",
                    "chargeType": "Peak-Usage",
                    "chargeCategoryCode": "USAGE",
                },
                {
                    "readDate": "2026-05-01",
                    "usage": 1.0,
                    "suffix": "E1",
                    "chargeType": "Peak Usage",
                    "chargeCategoryCode": "USAGE",
                },
                {"readDate": "2026-05-01", "usage": 1.0},
            ]
        }
    )

    slugs = {register["key"]: register["slug"] for register in usage["registers"]}
    assert slugs["unknown"] == "unknown"
    assert slugs["E1-Peak Usage"].startswith("e1_peak_usage_")
    assert slugs["E1-Peak-Usage"].startswith("e1_peak_usage_")
    assert slugs["E1-Peak Usage"] != slugs["E1-Peak-Usage"]

    # The suffix comes from the key alone, not from the other colliding key.
    alone = build_usage_summary(
        {
            "data": [
                {
                    "readDate": "2026-05-01",
                    "usage": 1.0,
                    "suffix": "E1",
                    "chargeType": "Peak-Usage",
                    "chargeCategoryCode": "USAGE",
                },
                {
                    "readDate": "2026-05-01",
                    "usage": 1.0,
                    "suffix": "e1",
                    "chargeType": "peak usage",
                    "chargeCategoryCode": "USAGE",
                },
            ]
        }
    )
    alone_slugs = {r["key"]: r["slug"] for r in alone["registers"]}
    assert alone_slugs["E1-Peak-Usage"] == slugs["E1-Peak-Usage"]


def test_cost_summary_exposes_new_category_totals() -> None:
    """Cost summaries preserve newer GloBird categories separately."""
    payload = {
        "data": [
            {
                "chargeCategory": "USAGE",
                "date": "2026/04/24",
                "amount": 1.2,
                "quantity": 3.0,
            },
            {
                "chargeCategory": "SOLAR",
                "date": "2026/04/24",
                "amount": -0.5,
                "quantity": 2.0,
            },
            {
                "chargeCategory": "Super Export top up",
                "date": "2026/04/24",
                "amount": -0.8,
                "quantity": 2.0,
            },
            {
                "chargeCategory": "ZEROHERO Credit",
                "date": "2026/04/24",
                "amount": -0.3,
                "quantity": 0.0,
            },
        ],
        "message": None,
        "success": True,
    }

    cost = build_cost_summary(payload)

    assert cost["total_amount"] == -0.4
    assert cost["latest_day_amount"] == -0.4
    assert cost["latest_day_zerohero_credit"] == -0.3
    assert cost["latest_day_zerohero_achieved"] is True
    assert cost["categories"] == [
        {"chargeCategory": "SOLAR", "amount": -0.5, "quantity": 2.0},
        {"chargeCategory": "Super Export top up", "amount": -0.8, "quantity": 2.0},
        {"chargeCategory": "USAGE", "amount": 1.2, "quantity": 3.0},
        {"chargeCategory": "ZEROHERO Credit", "amount": -0.3, "quantity": 0.0},
    ]


def test_cost_summary_exposes_daily_net_totals() -> None:
    """Billing calculations use daily net totals instead of rounded category rows."""
    payload = {
        "data": [
            {
                "chargeCategory": "USAGE",
                "date": "2026/06/01",
                "amount": 1.114,
                "quantity": 3.0,
            },
            {
                "chargeCategory": "SUPPLY",
                "date": "2026/06/01",
                "amount": 1.116,
                "quantity": 0.0,
            },
            {
                "chargeCategory": "SOLAR",
                "date": "2026/06/02",
                "amount": -0.224,
                "quantity": 1.5,
            },
            {
                "chargeCategory": "SUPPLY",
                "date": "2026/06/02",
                "amount": 1.116,
                "quantity": 0.0,
            },
        ],
        "message": None,
        "success": True,
    }

    cost = build_cost_summary(payload)

    assert cost["daily_totals"] == [
        {"date": "2026/06/01", "amount": 2.23},
        {"date": "2026/06/02", "amount": 0.89},
    ]


def test_billing_period_projection_uses_billing_days_not_calendar_month() -> None:
    """Expected monthly cost should align with the current billing cycle."""
    projection = build_billing_period_projection(
        [
            {"date": "2026/06/03", "amount": 10.0},
            {"date": "2026/06/04", "amount": 14.0},
            {"date": "2026/06/05", "amount": 6.0},
        ],
        date(2026, 6, 3),
        period_days=30,
    )

    assert projection == {
        "billing_period_start": "2026-06-03",
        "cost_to_date": 30.0,
        "projected_cost": 300.0,
        "completed_days": 3,
        "period_days": 30,
        "latest_day": "2026-06-05",
    }


def test_cost_summary_projects_current_month_cost() -> None:
    """Current-month projection extrapolates completed daily cost rows."""
    today = date.today()
    day_1 = today.replace(day=1)
    day_2 = day_1 + timedelta(days=1) if today.day > 1 else day_1
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    payload = {
        "data": [
            {
                "chargeCategory": "USAGE",
                "date": day_1.strftime("%Y/%m/%d"),
                "amount": 2.0,
                "quantity": 4.0,
            },
            {
                "chargeCategory": "SUPPLY",
                "date": day_1.strftime("%Y/%m/%d"),
                "amount": 1.0,
                "quantity": 0.0,
            },
            {
                "chargeCategory": "SOLAR",
                "date": day_2.strftime("%Y/%m/%d"),
                "amount": -1.0,
                "quantity": 2.0,
            },
        ],
        "message": None,
        "success": True,
    }

    cost = build_cost_summary(payload)

    assert cost["projected_month"] == {
        "month": today.strftime("%Y-%m"),
        "cost_to_date": 2.0,
        "projected_cost": round(2.0 / day_2.day * days_in_month, 2),
        "completed_days": day_2.day,
        "days_in_month": days_in_month,
        "latest_day": day_2.isoformat(),
    }


def test_sensor_attributes_are_recorder_safe_summaries() -> None:
    """Entity attributes keep recent rows only and strip nested register details."""
    usage_payload = {
        "data": [
            {
                "readDate": (date(2026, 4, 1) + timedelta(days=offset)).isoformat(),
                "usage": 1.0,
                "suffix": "E1",
                "chargeType": "Peak",
                "chargeCategoryCode": "USAGE",
                "usageArray": [0.1] * 48,
            }
            for offset in range(45)
        ],
    }
    cost_payload = {
        "data": [
            {
                "chargeCategory": category,
                "date": (date(2026, 4, 1) + timedelta(days=offset)).strftime(
                    "%Y/%m/%d"
                ),
                "amount": amount,
                "quantity": 1.0,
            }
            for offset in range(45)
            for category, amount in (
                ("USAGE", 1.1),
                ("SUPPLY", 1.2),
                ("SOLAR", -0.4),
            )
        ],
    }

    usage = usage_attributes(build_usage_summary(usage_payload), direction="import")
    cost = cost_attributes(build_cost_summary(cost_payload))

    assert usage["daily_count"] == 45
    assert len(usage["daily"]) == 7
    assert usage["daily_truncated"] is True
    assert "daily" not in usage["registers"][0]
    assert len(cost["daily"]) == 7
    assert len(cost["available_daily"]) == 7
    assert cost["daily_truncated"] is True
    assert len(json.dumps(usage)) < 16_384
    assert len(json.dumps(cost)) < 16_384


def test_redact_sensitive_diagnostics() -> None:
    """Diagnostics redaction removes credentials and account identifiers."""
    payload = {
        "emailAddress": "user@example.test",
        "password": "secret",
        "nested": {
            "accountNumber": "GB0001",
            "safe": "kept",
        },
        "items": [{"serialNumber": "meter-123"}, "ok"],
    }

    redacted = redact_sensitive(payload)

    assert redacted["emailAddress"] == "**REDACTED**"
    assert redacted["password"] == "**REDACTED**"
    assert redacted["nested"]["accountNumber"] == "**REDACTED**"
    assert redacted["nested"]["safe"] == "kept"
    assert redacted["items"] == [{"serialNumber": "**REDACTED**"}, "ok"]


def test_restore_session_success_and_failure() -> None:
    """restore_session should toggle authentication based on currentuser response."""
    success_session = FakeSession(
        [(200, {"data": {"emailAddress": "u"}, "success": True})]
    )
    success_client = GloBirdClient(
        session=success_session, base_url="https://example.test"
    )

    restored = asyncio.run(
        success_client.restore_session("user@example.test", "secret")
    )
    assert restored is not None
    assert success_client.is_authenticated is True

    failed_session = FakeSession([(500, {"success": False})])
    failed_client = GloBirdClient(
        session=failed_session, base_url="https://example.test"
    )
    restored_none = asyncio.run(
        failed_client.restore_session("user@example.test", "secret")
    )
    assert restored_none is None
    assert failed_client.is_authenticated is False


def test_service_endpoints_build_expected_paths() -> None:
    """Endpoint helpers should include optional query parameters."""
    session = FakeSession(
        [
            (200, {"success": True, "data": {}}),
            (200, {"success": True, "data": {}}),
            (200, {"success": True, "data": []}),
            (200, {"success": True, "data": {}}),
            (200, {"success": True, "data": {}}),
        ]
    )
    client = GloBirdClient(session=session, base_url="https://example.test")

    async def scenario() -> None:
        await client.get_dashboard(account_id=1)
        await client.get_balance(account_id=1)
        await client.get_signup_info(account_id=1)
        await client.get_power_meter_types(nmi="NMI-1")
        await client.get_read_meters(account_service_id=10)

    asyncio.run(scenario())

    assert session.requests[0][1].endswith("/api/account/dashboard?accountId=1")
    assert session.requests[1][1].endswith("/api/transaction/balance?accountId=1")
    assert session.requests[2][1].endswith("/api/account/getSignupInfo?accountId=1")
    assert session.requests[3][1].endswith("/api/site/GetPowerMeterTypes?nmi=NMI-1")
    assert session.requests[4][1].endswith("/api/site/readmeters?accountServiceId=10")


def test_cost_and_weather_requests_include_expected_payload_keys() -> None:
    """POST payloads should contain the required API fields."""
    session = FakeSession(
        [
            (200, {"success": True, "data": []}),
            (200, {"success": True, "data": []}),
        ]
    )
    client = GloBirdClient(session=session, base_url="https://example.test")

    async def scenario() -> None:
        await client.get_cost_detail(
            account_service_id=10,
            identifier="NMI-1",
            is_smart=True,
            days=3,
        )
        await client.get_weather_data(account_service_id=10, post_code="3000", days=3)

    asyncio.run(scenario())

    cost_payload = session.requests[0][2]["json"]
    weather_payload = session.requests[1][2]["json"]
    assert "from" in cost_payload and "to" in cost_payload
    assert cost_payload["accountServiceId"] == 10
    assert "dateFrom" in weather_payload and "dateTo" in weather_payload
    assert weather_payload["postCode"] == "3000"


def test_cookie_export_import_and_html_decode_roundtrip() -> None:
    """Cookie helpers should export/import values and HTML-decoded JSON."""

    class FakeCookie:
        def __init__(self, name: str, value: str) -> None:
            self.key = name
            self.value = value
            self._meta = {
                "domain": "example.test",
                "path": "/",
                "secure": True,
                "httponly": True,
            }

        def __getitem__(self, key: str) -> Any:
            return self._meta[key]

    class FakeCookieJar:
        def __init__(self) -> None:
            self._cookies = [FakeCookie("ARRAffinity", "abc")]

        def __iter__(self) -> Any:
            return iter(self._cookies)

        def update_cookies(self, _cookies: Any, _url: Any) -> None:
            return None

    session = FakeSession([])
    session.cookie_jar = FakeCookieJar()
    client = GloBirdClient(session=session, base_url="https://example.test")

    client.import_session_cookies(
        [
            {
                "name": "ARRAffinity",
                "value": "abc",
                "domain": "example.test",
                "path": "/",
                "secure": "True",
                "httponly": "True",
            }
        ]
    )
    exported = client.export_session_cookies()
    assert any(cookie["name"] == "ARRAffinity" for cookie in exported)

    decoded = GloBirdClient.decode_html_json("{&quot;a&quot;: 1}")
    assert decoded == {"a": 1}


def test_small_helper_edge_cases() -> None:
    """Exercise helper fallback branches for parser and summary helpers."""
    assert api_impl._as_float(None) is None
    assert api_impl._as_float("x") is None
    assert api_impl._round(None) is None
    assert api_impl._payload_data(None) is None
    assert api_impl._date_key({"a": None}, "a", "b") == ""
    assert api_impl._parse_date("not-a-date") is None
    assert api_impl._recent_rows("bad") == []
    assert (
        api_impl._usage_latest_day({"latest_day": "2026-01-01"}, ["bad"])
        == "2026-01-01"
    )
    assert api_impl._meter_status_rank({}) == 2
    assert api_impl._meter_status_rank({"serialStatus": "mystery"}) == 1
    assert api_impl._meter_type_rank({}) == 0


def test_select_meter_supports_nested_wrapped_lists() -> None:
    """Meter payload wrapper keys should be handled consistently."""
    selected = select_meter_for_service(
        {"siteIdentifier": "NMI-X"},
        {"data": {"readMeters": [{"siteIdentifier": "NMI-X", "serialNumber": "m1"}]}},
    )
    assert selected is not None
    assert selected["serialNumber"] == "m1"


def test_global_summary_defaults_without_payloads() -> None:
    """Global summary should return stable defaults for missing payloads."""
    summary = api.build_global_summary(
        None,
        None,
        None,
        last_update=None,
        last_failed_update=None,
        refresh_error="err",
        fetch_errors=None,
    )
    assert summary["refresh_status"] == "error"
    assert summary["signup_services"] == 0
    assert summary["signup_info"] == []


def test_raw_request_json_error_modes() -> None:
    """HTTP/auth/json/payload failure branches should raise API errors."""
    client = GloBirdClient(
        session=FakeSession([(403, {"success": False})]),
        base_url="https://example.test",
    )
    try:
        asyncio.run(client._raw_request_json("GET", "/x"))
    except api.GloBirdSessionExpired:
        pass
    else:
        raise AssertionError("Expected session-expired error")

    client = GloBirdClient(
        session=FakeSession([(500, {"success": False})]),
        base_url="https://example.test",
    )
    try:
        asyncio.run(client._raw_request_json("GET", "/x"))
    except api.GloBirdApiError:
        pass
    else:
        raise AssertionError("Expected HTTP API error")

    class InvalidJsonResponse(FakeResponse):
        async def text(self) -> str:
            return "{oops"

    class InvalidJsonSession(FakeSession):
        def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
            self.requests.append((method, url, kwargs))
            return InvalidJsonResponse(200, {})

    client = GloBirdClient(
        session=InvalidJsonSession([]), base_url="https://example.test"
    )
    try:
        asyncio.run(client._raw_request_json("GET", "/x"))
    except api.GloBirdApiError:
        pass
    else:
        raise AssertionError("Expected invalid JSON API error")

    client = GloBirdClient(
        session=FakeSession([(200, {"success": False, "message": "nope"})]),
        base_url="https://example.test",
    )
    try:
        asyncio.run(client._raw_request_json("GET", "/x"))
    except api.GloBirdApiError:
        pass
    else:
        raise AssertionError("Expected payload failure API error")

    client = GloBirdClient(
        session=FakeSession([(200, {"success": False, "message": "ok to pass"})]),
        base_url="https://example.test",
    )
    payload = asyncio.run(client._raw_request_json("GET", "/x", allow_api_failure=True))
    assert payload["success"] is False


def test_request_json_no_retry_when_auth_not_possible() -> None:
    """Request wrapper should re-raise expiry when retry preconditions fail."""
    client = GloBirdClient(session=FakeSession([]), base_url="https://example.test")

    async def raise_expired(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        raise api.GloBirdSessionExpired("expired")

    client._raw_request_json = raise_expired  # type: ignore[method-assign]
    try:
        asyncio.run(client._request_json("GET", "/x", retry_auth=False))
    except api.GloBirdSessionExpired:
        pass
    else:
        raise AssertionError("Expected session-expired re-raise")


def test_establish_session_handles_sticky_and_exceptions() -> None:
    """Session establishment should copy sticky cookies and swallow failures."""

    class Cookie:
        def __init__(self, key: str, value: str) -> None:
            self.key = key
            self.value = value

    class CookieJar:
        def __init__(self) -> None:
            self.updated = None

        def __iter__(self) -> Any:
            return iter([Cookie("ARRAffinity", "abc")])

        def update_cookies(self, cookies: Any, primary: Any) -> None:
            self.updated = (cookies, primary)

    class Resp(FakeResponse):
        async def read(self) -> bytes:
            return b"ok"

    class GoodSession(FakeSession):
        def __init__(self) -> None:
            super().__init__([])
            self.cookie_jar = CookieJar()

        def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
            self.requests.append((method, url, kwargs))
            return Resp(200, {})

    good = GoodSession()
    client = GloBirdClient(session=good, base_url="https://example.test")
    asyncio.run(client._establish_session())
    assert good.cookie_jar.updated is not None

    class BadSession(GoodSession):
        def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
            raise RuntimeError("network")

    bad = BadSession()
    client = GloBirdClient(session=bad, base_url="https://example.test")
    asyncio.run(client._establish_session())


def test_authenticate_login_failure_with_message() -> None:
    """Failed login should include portal message and keep auth false."""
    session = FakeSession(
        [
            (
                200,
                {
                    "success": False,
                    "message": "bad creds",
                    "data": {"isLoginSucceeded": False},
                },
            ),
        ]
    )
    client = GloBirdClient(session=session, base_url="https://example.test")
    stub_password_encryption(client)
    try:
        asyncio.run(
            client.authenticate("user@example.test", "wrong", fresh_session=False)
        )
    except api.GloBirdAuthError as err:
        assert "bad creds" in str(err)
    else:
        raise AssertionError("Expected auth error")
    assert client.is_authenticated is False


def test_pydantic_models_and_client_additional_coverage() -> None:
    """Test Pydantic v2 field validators, RSA JWK encryption, and client endpoint helpers."""
    import base64

    from cryptography.hazmat.primitives.asymmetric import rsa

    from custom_components.globird.api.models import (
        UsageDailyRow,
        _coerce_optional_float,
    )

    assert _coerce_optional_float(None) is None
    assert _coerce_optional_float(True) is None
    assert _coerce_optional_float(" 12.34 ") == 12.34
    assert _coerce_optional_float("   ") is None
    assert _coerce_optional_float("not-a-float") is None
    assert _coerce_optional_float(["invalid"]) is None
    row = UsageDailyRow.model_validate({"readDate": "2026-09-28", "usage": "4.5"})
    assert row.usage == 4.5

    # Generate an ephemeral RSA key to test _encrypt_password end-to-end
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub_numbers = private_key.public_key().public_numbers()
    n_bytes = pub_numbers.n.to_bytes((pub_numbers.n.bit_length() + 7) // 8, "big")
    e_bytes = pub_numbers.e.to_bytes((pub_numbers.e.bit_length() + 7) // 8, "big")
    jwk_payload = {
        "n": base64.urlsafe_b64encode(n_bytes).decode("utf-8").rstrip("="),
        "e": base64.urlsafe_b64encode(e_bytes).decode("utf-8").rstrip("="),
    }

    session = FakeSession(
        [
            (200, jwk_payload),
            (200, {"data": {"user": 1}, "success": True}),
            (200, {"data": {}, "success": True}),
            (200, {"data": [], "success": True}),
            (200, {"data": {"days": 2}, "success": True}),
            (200, {"data": {"days": 3}, "success": True}),
        ]
    )
    client = GloBirdClient(session=session, base_url="https://example.test")
    encrypted = asyncio.run(client._encrypt_password("secret-pw"))
    assert isinstance(encrypted, str) and len(encrypted) > 20

    client.disable_reauth()
    client.enable_reauth()
    assert asyncio.run(client.get_current_user())["success"] is True
    assert asyncio.run(client.get_account_service_status())["success"] is True
    assert asyncio.run(client.get_power_meter_types(nmi="123"))["success"] is True
    assert asyncio.run(client.get_weather_impacted_days())["success"] is True
    assert (
        asyncio.run(client.get_weather_impacted_days(account_id=42))["success"] is True
    )

    async def owned_session_lifecycle() -> None:
        owned = GloBirdClient()
        await owned.close()

    asyncio.run(owned_session_lifecycle())

    # Additional edge cases in select_meter_for_service, build_usage_summary, build_gas_reading_summary, and build_billing_period_projection
    assert (
        select_meter_for_service({"siteIdentifier": "NMI"}, {"data": "invalid"}) is None
    )
    assert (
        select_meter_for_service({"siteIdentifier": "NMI"}, {"data": {"items": []}})
        is None
    )
    assert build_usage_summary({"data": "not-a-list"})["days"] == 0
    assert (
        build_gas_reading_summary(
            {
                "data": {
                    "src1": "not-a-list",
                    "src2": ["not-a-dict", {"readIndex": None, "readDate": "bad"}],
                }
            }
        )["history_count"]
        == 0
    )
    assert build_cost_summary({"data": "not-a-list"})["days"] == 0
    assert (
        build_billing_period_projection(
            ["not-a-dict", {"date": "2020-01-01", "amount": 5.0}],
            date(2026, 1, 1),
        )["completed_days"]
        == 0
    )
    assert all_services_ready_for_day(None, date(2026, 1, 1)) is False
    assert all_services_ready_for_day({"a": "not-dict"}, date(2026, 1, 1)) is False
    assert (
        all_services_ready_for_day(
            {"a": {"latest_data_status": None}}, date(2026, 1, 1)
        )
        is False
    )


def load_tests(
    _loader: unittest.TestLoader,
    _tests: unittest.TestSuite,
    _pattern: str | None,
) -> unittest.TestSuite:
    """Expose pytest-style functions to the stdlib unittest runner."""
    suite = unittest.TestSuite()
    for test_func in (
        test_authenticate_success,
        test_authenticate_captcha_required,
        test_authenticate_invalid_credentials,
        test_session_expiry_reauthenticates_once,
        test_get_usage_uses_basic_meter_endpoint_for_non_smart_meter,
        test_extract_accounts_services_and_summaries,
        test_extract_accounts_and_services_includes_active_gas_services,
        test_select_meter_rejects_another_services_identified_meter,
        test_build_gas_reading_summary_tracks_latest_reading_and_history,
        test_cost_summary_net_daily_is_sum_not_last_row,
        test_cost_summary_ignores_supply_only_partial_latest_day,
        test_usage_summary_tracks_all_registers_and_b_exports,
        test_usage_summary_keeps_solar_soak_import_register_out_of_export,
        test_usage_summary_excludes_zerohero_reward_registers_live_shape,
        test_usage_summary_latest_intervals_count_each_meter_channel_once,
        test_usage_summary_sums_intervals_that_differ_per_row,
        test_cost_usage_quantities_match_energy_registers_live_shape,
        test_usage_registers_expose_time_periods_daily_and_sensor_flag,
        test_flat_rate_registers_get_no_register_sensor,
        test_usage_attributes_list_export_registers_for_export_sensors,
        test_usage_classification_edge_cases,
        test_usage_summary_with_only_tracking_rows_keeps_registers,
        test_controlled_load_registers_are_split_from_general_import,
        test_register_slugs_stay_unique,
        test_cost_summary_exposes_new_category_totals,
        test_cost_summary_projects_current_month_cost,
        test_sensor_attributes_are_recorder_safe_summaries,
        test_redact_sensitive_diagnostics,
    ):
        suite.addTest(unittest.FunctionTestCase(test_func))
    return suite
